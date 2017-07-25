# -*- coding: utf-8 -*-
from __future__ import absolute_import, division

import pytest
import mock
import nfc

import logging
logging.basicConfig(level=logging.DEBUG-1)
logging_level = logging.getLogger().getEffectiveLevel()
logging.getLogger("nfc.snep").setLevel(logging_level)


def HEX(s):
    return bytearray.fromhex(s)


@pytest.fixture()
def socket(mocker):
    return mocker.patch('nfc.llcp.Socket', autospec=True)


@pytest.fixture()
def dlc(mocker):
    return nfc.llcp.tco.DataLinkConnection(128, 10)


@pytest.fixture()
def llc(mocker, dlc):
    mocker.patch('nfc.llcp.llc.LogicalLinkController', autospec=True)
    llc = nfc.llcp.llc.LogicalLinkController()
    llc.socket.return_value = dlc
    return llc


@pytest.mark.parametrize("args, service_name", [
    ((), b'urn:nfc:sn:snep'),
    ((b'urn:nfc:sn:snep',), b'urn:nfc:sn:snep'),
    ((b'urn:nfc:xsn:nfcpy.org:snep',), b'urn:nfc:xsn:nfcpy.org:snep'),
])
def test_connect(llc, dlc, args, service_name):
    client = nfc.snep.SnepClient(llc)
    client.connect(*args)
    llc.connect.assert_called_once_with(dlc, service_name)
    llc.getsockopt.assert_called_once_with(dlc, nfc.llcp.SO_SNDMIU)


def test_close(llc, dlc):
    client = nfc.snep.SnepClient(llc)
    client.connect()
    socket = client.socket
    client.close()
    llc.connect.assert_called_once_with(dlc, b'urn:nfc:sn:snep')
    llc.getsockopt.assert_called_once_with(dlc, nfc.llcp.SO_SNDMIU)
    llc.close.assert_called_once_with(dlc)
