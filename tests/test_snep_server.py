# -*- coding: utf-8 -*-
from __future__ import absolute_import, division

import pytest
import errno
import time
import mock
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


def test_init_start(mocker, llc):
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


def test_accept_start(mocker, llc):
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
    snep_server.listen(snep_socket)
    time.sleep(0.01)
    client_socket.getpeername.assert_called_once()
    client_socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    client_socket.recv.assert_called_once()


def test_serve_dlc_closed(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    server = nfc.snep.SnepServer(llc)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'recv').return_value = None
    nfc.snep.SnepServer.serve(socket, server)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.recv.assert_called_once()


def test_serve_bad_client(mocker, llc):
    socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
    server = nfc.snep.SnepServer(llc)
    mocker.patch.object(socket, 'getpeername').return_value = 32
    mocker.patch.object(socket, 'getsockopt').return_value = 128
    mocker.patch.object(socket, 'recv').return_value = b'12345'
    nfc.snep.SnepServer.serve(socket, server)
    socket.getpeername.assert_called_once()
    socket.getsockopt.assert_called_once_with(nfc.llcp.SO_SNDMIU)
    socket.recv.assert_called_once()
