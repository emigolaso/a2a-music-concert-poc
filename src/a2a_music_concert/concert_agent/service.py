from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from html import unescape
from typing import TypedDict
from urllib.parse import urlparse

import httpx
from langgraph.graph import END, START, StateGraph
from litellm import acompletion

from a2a_music_concert.shared.config import get_settings

PRIORITY_DOMAINS = (
    "ticketmaster.com",
    "bandsintown.com",
    "songkick.com",
    "seatgeek.com",
    "stubhub.com",
    "yeezy.com",
    "tour.yeezy.com",
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    domain: str


class SearchPlan(TypedDict):
    should_search: bool
    search_queries: list[str]
    response_if_not_search: str | None


class ConcertState(TypedDict, total=False):
    question: str
    plan: SearchPlan
    search_results: list[SearchResult]
    answer: str


def _normalize_question(question: str) -> str:
    cleaned = question.strip()
    cleaned = re.sub(r"^\s*User asks:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or question


def _watsonx_model_name() -> str:
    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("WATSONX_PROJECT_ID", settings.watsonx_project_id),
            ("WATSONX_APIKEY", settings.watsonx_apikey),
            ("WATSONX_URL", settings.watsonx_url),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing watsonx configuration: {', '.join(missing)}")
    os.environ["WATSONX_PROJECT_ID"] = settings.watsonx_project_id
    os.environ["WATSONX_APIKEY"] = settings.watsonx_apikey
    os.environ["WATSONX_URL"] = settings.watsonx_url
    return f"watsonx/{settings.watsonx_model_id}"


async def _build_search_plan(question: str) -> SearchPlan:
    prompt = _normalize_question(question)
    response = await acompletion(
        model=_watsonx_model_name(),
        api_key=get_settings().watsonx_apikey,
        base_url=get_settings().watsonx_url,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You create web search queries for a concert-search agent. "
                    "Return only JSON with keys: should_search, search_queries, response_if_not_search. "
                    "If the user's message is about concerts, tours, live shows, tickets, or upcoming performances for one or more artists, set should_search=true. "
                    "Then produce 2 to 4 focused web search queries based directly on the user's wording. "
                    "Keep artist names exactly as written by the user, including punctuation like J. Cole, A$AP Rocky, or P!nk. "
                    "If there is a location like NYC or New York, include it in at least one query. "
                    "Prefer concert-oriented search terms and source-focused queries like ticketmaster, bandsintown, songkick, seatgeek, or stubhub. "
                    "If the user's message is not about artist concerts or live shows, set should_search=false and provide a short friendly response_if_not_search explaining that this agent only handles concert lookups for artists."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    data = _extract_json_object(response.choices[0].message.content or "{}")
    queries = [query.strip() for query in data.get("search_queries", []) if str(query).strip()]
    return {
        "should_search": bool(data.get("should_search")),
        "search_queries": queries,
        "response_if_not_search": data.get("response_if_not_search"),
    }


def _extract_json_object(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
    raise ValueError(f"Could not parse concert-agent planner output: {raw}")


async def _plan_search(state: ConcertState) -> ConcertState:
    return {"plan": await _build_search_plan(state["question"])}


def _route_after_plan(state: ConcertState) -> str:
    plan = state["plan"]
    if not plan["should_search"] or not plan["search_queries"]:
        return "format_answer"
    return "search_web"


def _domain_rank(url: str) -> tuple[int, str]:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    for index, preferred in enumerate(PRIORITY_DOMAINS):
        if preferred in domain:
            return (index, domain)
    return (len(PRIORITY_DOMAINS), domain)


def _search_web(state: ConcertState) -> ConcertState:
    deduped: dict[str, SearchResult] = {}
    for query in state["plan"]["search_queries"]:
        results = _search_duckduckgo(query, max_results=5)
        if not results:
            results = _search_bing(query, max_results=5)
        for result in results:
            deduped.setdefault(result.url, result)
    ordered = sorted(deduped.values(), key=lambda result: (_domain_rank(result.url), result.title))
    return {"search_results": ordered[:8]}


def _search_duckduckgo(query: str, *, max_results: int) -> list[SearchResult]:
    response = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    html = response.text

    blocks = re.findall(
        r'(<div class="result results_links.*?</div>\s*</div>)',
        html,
        flags=re.DOTALL,
    )
    results: list[SearchResult] = []
    for block in blocks:
        title_match = re.search(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', block, flags=re.DOTALL)
        snippet_match = re.search(r'<a class="result__snippet".*?>(.*?)</a>', block, flags=re.DOTALL)
        if not title_match:
            continue
        url = _decode_duckduckgo_redirect(unescape(title_match.group(1)))
        title = _clean_html(title_match.group(2))
        snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""
        if not url or not title:
            continue
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                domain=urlparse(url).netloc.lower().removeprefix("www."),
            )
        )
        if len(results) >= max_results:
            break
    return results


def _search_bing(query: str, *, max_results: int) -> list[SearchResult]:
    response = httpx.get(
        "https://www.bing.com/search",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    html = response.text

    blocks = re.findall(
        r'(<li class="b_algo".*?)(?=<li class="b_algo"|<nav role="navigation"|</ol>)',
        html,
        flags=re.DOTALL,
    )
    results: list[SearchResult] = []
    for block in blocks:
        title_match = re.search(r'<h2[^>]*><a [^>]*>(.*?)</a></h2>', block, flags=re.DOTALL)
        cite_match = re.search(r"<cite>(.*?)</cite>", block, flags=re.DOTALL)
        snippet_match = re.search(r'<div class="b_caption"><p[^>]*>(.*?)</p>', block, flags=re.DOTALL)
        if not title_match or not cite_match:
            continue

        url = _clean_cite(cite_match.group(1))
        title = _clean_html(title_match.group(1))
        snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""
        if not url or not title:
            continue

        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                domain=urlparse(url).netloc.lower().removeprefix("www."),
            )
        )
        if len(results) >= max_results:
            break
    return results


def _format_answer(state: ConcertState) -> ConcertState:
    plan = state["plan"]
    if not plan["should_search"]:
        return {
            "answer": plan.get("response_if_not_search")
            or "I handle concert lookups for artists. Ask me about upcoming shows for one or more artists."
        }

    results = state.get("search_results", [])
    if not results:
        return {
            "answer": (
                "I couldn't confirm likely concert listings from search results right now. "
                "Try again later or add an artist/location to narrow it down."
            )
        }

    lines = ["Here are the most likely concert listings I found:"]
    for index, result in enumerate(results[:5], start=1):
        line = f"{index}. {result.title} ({result.domain})"
        if result.snippet:
            line += f" — {result.snippet}"
        line += f" [{result.url}]"
        lines.append(line)
    lines.append("These are search-based results, so confirm dates on the venue or ticketing page.")
    return {"answer": "\n".join(lines)}


def _clean_html(value: str) -> str:
    text = re.sub(r"<.*?>", "", value, flags=re.DOTALL)
    return unescape(" ".join(text.split()))


def _clean_cite(value: str) -> str:
    cite = _clean_html(value).replace(" › ", "/")
    cite = cite.replace("…", "").strip()
    if not cite:
        return ""
    if cite.startswith("http://") or cite.startswith("https://"):
        return cite
    return f"https://{cite}"


def _decode_duckduckgo_redirect(url: str) -> str:
    if "uddg=" not in url:
        if url.startswith("//"):
            return f"https:{url}"
        return url
    match = re.search(r"[?&]uddg=([^&]+)", url)
    if not match:
        return url
    from urllib.parse import unquote

    return unquote(match.group(1))


def build_concert_graph():
    graph = StateGraph(ConcertState)
    graph.add_node("plan_search", _plan_search)
    graph.add_node("search_web", _search_web)
    graph.add_node("format_answer", _format_answer)
    graph.add_edge(START, "plan_search")
    graph.add_conditional_edges(
        "plan_search",
        _route_after_plan,
        {
            "search_web": "search_web",
            "format_answer": "format_answer",
        },
    )
    graph.add_edge("search_web", "format_answer")
    graph.add_edge("format_answer", END)
    return graph.compile()


async def answer_concert_question(question: str) -> str:
    graph = build_concert_graph()
    result = await graph.ainvoke({"question": question})
    return result["answer"]
