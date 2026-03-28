from a2a_music_concert.shared.models import ConcertAgentResponse, MusicAgentResponse
from a2a_music_concert.concert_agent.service import _clean_cite, _normalize_question


def test_music_response_shape():
    payload = MusicAgentResponse(
        artist_name="Bad Bunny",
        artist_id="abc123",
        source_summary="Derived from your Spotify short_term top artists.",
        time_range="short_term",
    )
    assert payload.artist_name == "Bad Bunny"


def test_concert_response_empty_case():
    payload = ConcertAgentResponse(status="none_found", artist_name="Unknown", events=[])
    assert payload.status == "none_found"
    assert payload.events == []


def test_normalize_question_strips_wrapper():
    assert _normalize_question("User asks: Are there any J. Cole concerts?") == "Are there any J. Cole concerts?"


def test_clean_cite_restores_url_shape():
    assert _clean_cite("seatgeek.com › ye-tickets") == "https://seatgeek.com/ye-tickets"
