from a2a_music_concert.a2a.executors import _render_music_response
from a2a_music_concert.shared.models import MusicAgentResponse


def test_render_music_response_prefers_message() -> None:
    response = MusicAgentResponse(
        answer_type="artist_answer",
        message="Your top 3 all-time played artists are:\n1. J. Cole\n2. ERNEST\n3. Kanye West",
        artist_name="J. Cole",
    )

    assert _render_music_response(response) == response.message


def test_render_music_response_does_not_prefix_artist_name() -> None:
    response = MusicAgentResponse(
        answer_type="artist_answer",
        message=None,
        artist_name="J. Cole",
    )

    assert _render_music_response(response) == "J. Cole"
