"""Response decoding: the board mixes stray cp1252 bytes into otherwise UTF-8 bodies."""

import httpx2

from wwlocal.waterlooworks import _json, _text


def _response(body: bytes, content_type: str = "application/json") -> httpx2.Response:
    return httpx2.Response(200, content=body, headers={"Content-Type": content_type})


def test_utf8_body_is_unchanged():
    assert _json(_response('{"city": "Montréal"}'.encode())) == {"city": "Montréal"}


def test_stray_cp1252_byte_does_not_break_json():
    # 0xdf is "ß" in cp1252; the rest of the body is real UTF-8.
    body = '{"org": "Gro\udcdfmann", "city": "Montréal"}'.encode("utf-8", "surrogateescape")
    assert _json(_response(body)) == {"org": "Großmann", "city": "Montréal"}


def test_declared_latin1_charset_is_honoured():
    body = '{"org": "Großmann"}'.encode("cp1252")
    r = _response(body, "application/json; charset=ISO-8859-1")
    assert _json(r) == {"org": "Großmann"}


def test_undecodable_byte_becomes_replacement_char():
    assert _text(_response(b'{"a": "\x81"}')) == '{"a": "�"}'
