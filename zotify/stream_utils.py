"""Helpers for validating the payload exposed by a Spotify audio stream."""


def mark_stream_prefix_skipped(stream, byte_count: int) -> None:
    """Record how many leading bytes the caller already consumed from a stream."""
    if byte_count < 0 or byte_count > stream.size:
        raise ValueError("Skipped stream prefix is outside the declared stream size")
    stream._zotify_expected_size = stream.size - byte_count


def expected_stream_size(stream) -> int:
    """Return bytes remaining in the underlying stream, including implicit skips."""
    try:
        available = stream.stream().available()
    except (AttributeError, TypeError):
        available = None
    if isinstance(available, int) and available >= 0:
        return available
    return getattr(stream, "_zotify_expected_size", stream.size)
