# -*- coding: utf-8 -*-
from __future__ import absolute_import, division

import pytest
import errno
import time
import mock
import ndef
import nfc

import logging
logging.basicConfig(level=logging.DEBUG-1)
logging_level = logging.getLogger().getEffectiveLevel()
logging.getLogger("nfc.snep").setLevel(logging_level)


def HEX(s):
    return bytearray.fromhex(s)


@pytest.fixture
def llc():
    mac = mock.create_autospec(nfc.dep.Initiator)
    mac.rwt = 0.07
    mac.activate.return_value = HEX('46666d 010113 02020078 040132')
    llc = nfc.llcp.llc.LogicalLinkController()
    assert llc.activate(mac, brs=0) is True
    return llc


def test_init_custom_class(mocker, llc):
    class MySnepServer(nfc.snep.SnepServer):
        def get_records(self, *args, **kwargs):
            return mock.sentinel.get_records

        def put_records(self, *args, **kwargs):
            return mock.sentinel.put_records

        def get_octets(self, *args, **kwargs):
            return mock.sentinel.get_octets

        def put_octets(self, *args, **kwargs):
            return mock.sentinel.put_octets

    mocker.spy(llc, 'socket')
    mocker.spy(llc, 'bind')
    mocker.spy(llc, 'listen')
    server = MySnepServer(llc)
    llc.socket.assert_called_once_with(nfc.llcp.DATA_LINK_CONNECTION)
    llc.bind.assert_called_once_with(mock.ANY, b'urn:nfc:sn:snep')
    llc.listen.assert_called_once_with(mock.ANY, 2)
    assert server.get_records() == mock.sentinel.get_records
    assert server.put_records() == mock.sentinel.put_records
    assert server.get_octets() == mock.sentinel.get_octets
    assert server.put_octets() == mock.sentinel.put_octets


def test_set_callback(mocker, llc):
    mocker.spy(llc, 'socket')
    mocker.spy(llc, 'bind')
    mocker.spy(llc, 'listen')
    server = nfc.snep.SnepServer(llc)
    server.set_callback(get_records=mock.sentinel.get_records)
    server.set_callback(put_records=mock.sentinel.put_records)
    server.set_callback(get_octets=mock.sentinel.get_octets)
    server.set_callback(put_octets=mock.sentinel.put_octets)
    llc.socket.assert_called_once_with(nfc.llcp.DATA_LINK_CONNECTION)
    llc.bind.assert_called_once_with(mock.ANY, b'urn:nfc:sn:snep')
    llc.listen.assert_called_once_with(mock.ANY, 2)
    assert server.get_records == mock.sentinel.get_records
    assert server.put_records == mock.sentinel.put_records
    assert server.get_octets == mock.sentinel.get_octets
    assert server.put_octets == mock.sentinel.put_octets


def test_init_start_main_thread(mocker, llc):
    mocker.spy(llc, 'socket')
    mocker.spy(llc, 'bind')
    mocker.spy(llc, 'listen')
    mocker.patch.object(llc, 'accept')
    llc.accept.side_effect = nfc.llcp.Error(errno.EPIPE)
    nfc.snep.SnepServer(llc).start()
    time.sleep(0.01)
    llc.socket.assert_called_once_with(nfc.llcp.DATA_LINK_CONNECTION)
    llc.bind.assert_called_once_with(mock.ANY, b'urn:nfc:sn:snep')
    llc.listen.assert_called_once_with(mock.ANY, 2)
    llc.accept.assert_called_once_with(mock.ANY)


def test_accept_start_client_thread(mocker, llc):
    snep_server = nfc.snep.SnepServer(llc)
    snep_socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    snep_socket.bind(b'urn:nfc:xsn:nfcpy.org:snep')
    snep_socket.listen(backlog=1)
    client_socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(snep_socket, 'accept')
    snep_socket.accept.side_effect = [
        client_socket, nfc.llcp.Error(errno.EPIPE)
    ]
    mocker.patch.object(client_socket, 'getpeername')
    client_socket.getpeername.return_value = 32
    mocker.patch.object(client_socket, 'getsockopt')
    client_socket.getsockopt.return_value = 128
    mocker.patch.object(client_socket, 'recv')
    client_socket.recv.side_effect = nfc.llcp.Error(errno.EPIPE)
    snep_server._listen(snep_socket)
    time.sleep(0.01)
    client_socket.getpeername.assert_called_once()
    client_socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    client_socket.recv.assert_called_once()


def test_serve_dlc_closed(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'recv').return_value = None
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.recv.assert_called_once()


def test_serve_bad_client(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'recv').return_value = b'12345'
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.recv.assert_called_once()


def test_serve_unsupported_version(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('20 01 00000007 00000400 d00000'), None
    ]
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 e1 00000000'))


def test_serve_unacceptable_length(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 01 00000007 00000400 d00000'), None
    ]
    nfc.snep.SnepServer(llc, max_acceptable_length=6)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 ff 00000000'))


def test_serve_bad_request(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 00 00000007 00000400 d00000'), None
    ]
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 c2 00000000'))


def test_serve_request_remaining_but_closed(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 01 00000007 00000400'), HEX(''), None
    ]
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 80 00000000'))
    assert socket.recv.call_count == 3


def test_serve_get_not_implemented(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 01 00000007 00000400 d00000'), None
    ]
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 e0 00000000'))


def test_serve_get_short_request_response(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 01 00000007 00000400 d00000'), None
    ]
    records = [ndef.TextRecord('0123456789')]
    nfc.snep.SnepServer(llc, get_records=lambda req: records)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(
        HEX('10 81 00000011 d1010d5402656e30313233343536373839'))


def test_serve_get_long_request_response(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 16
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 01 00000007 00000400'), HEX('d00000'),
        HEX('10 00 00000000'), None
    ]
    records = [ndef.TextRecord('0123456789')]
    nfc.snep.SnepServer(llc, get_records=lambda req: records)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_has_calls([
        mock.call(HEX('10 80 00000000')),
        mock.call(HEX('10 81 00000011 d1010d5402656e303132')),
        mock.call(HEX('33343536373839')),
    ])


def test_serve_get_with_response_rejected(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 16
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 01 00000007 00000400 d00000'),
        HEX('10 7f 00000000'), None
    ]
    records = [ndef.TextRecord('0123456789')]
    nfc.snep.SnepServer(llc, get_records=lambda req: records)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_has_calls([
        mock.call(HEX('10 81 00000011 d1010d5402656e303132')),
    ])


def test_serve_get_unacceptable_length(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 01 00000007 00000010 d00000'), None
    ]
    records = [ndef.TextRecord('0123456789')]
    nfc.snep.SnepServer(llc, get_records=lambda req: records)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 c1 00000000'))


def test_serve_get_decode_error(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 01 00000006 00000400 d000'), None
    ]
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 c2 00000000'))


def test_serve_put_short_message(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 02 00000011 d1010d5402656e30313233343536373839'), None
    ]
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 81 00000000'))


def test_serve_put_long_message(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 02 00000011 d1010d5402656e303132'),
        HEX('33343536373839'), None
    ]
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_has_calls([
        mock.call(HEX('10 80 00000000')),
        mock.call(HEX('10 81 00000000')),
    ])


def test_serve_put_returns_error(mocker, llc):
    def put_records(request_records):
        raise nfc.snep.SnepError(0xC0)

    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 02 00000011 d1010d5402656e30313233343536373839'), None
    ]
    nfc.snep.SnepServer(llc, put_records=put_records)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 C0 00000000'))


def test_serve_put_decode_error(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'send').return_value = True
    mocker.patch.object(socket, 'recv').side_effect = [
        HEX('10 02 00000006 00000400 d000'), None
    ]
    nfc.snep.SnepServer(llc)._serve(socket)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.send.assert_called_once_with(HEX('10 c2 00000000'))
