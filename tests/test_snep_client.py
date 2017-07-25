# -*- coding: utf-8 -*-
from __future__ import absolute_import, division

import pytest
import mock
import ndef
import nfc

import logging
logging.basicConfig(level=logging.DEBUG-1)
logging_level = logging.getLogger().getEffectiveLevel()
logging.getLogger("nfc.snep").setLevel(logging_level)


def HEX(s):
    return bytearray.fromhex(s)


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
    client.close()
    llc.connect.assert_called_once_with(dlc, service_name)
    llc.getsockopt.assert_called_once_with(dlc, nfc.llcp.SO_SNDMIU)
    llc.close.assert_called_once_with(dlc)


@pytest.mark.parametrize("snep_req, ndef_req, snep_rsp, ndef_rsp", [
    ('10 01 00000007 00000400 d00000', None,
     '10 81 00000003 d00000', [ndef.Record()]),
    ('10 01 0000000c 00000400 d101045402656e61', [ndef.TextRecord('a')],
     '10 81 00000008 d101045402656e62', [ndef.TextRecord('b')]),
    ('10 01 00000007 00000400 d00000', [ndef.Record()],
     '10 81 00000002 d000', None),
    ('10 01 00000007 00000400 d00000', [ndef.Record()],
     '', None),
])
def test_get_records(llc, dlc, snep_req, ndef_req, snep_rsp, ndef_rsp):
    llc.send.return_value = True
    llc.poll.return_value = True
    llc.recv.return_value = HEX(snep_rsp)
    assert nfc.snep.SnepClient(llc).get_records(ndef_req) == ndef_rsp
    llc.connect.assert_called_once_with(dlc, b'urn:nfc:sn:snep')
    llc.send.assert_called_once_with(dlc, HEX(snep_req), 0)
    llc.poll.assert_called_once_with(dlc, 'recv', 1.0)
    llc.recv.assert_called_once_with(dlc)
    llc.close.assert_called_once_with(dlc)


@pytest.mark.parametrize("snep_req, ndef_req, snep_rsp, result", [
    ('10 02 00000003 d00000', [ndef.Record()],
     '10 81 00000000', True),
    ('10 02 00000008 d101045402656e61', [ndef.TextRecord('a')],
     '10 81 00000000', True),
    ('10 02 00000008 d101045402656e61', [ndef.TextRecord('a')],
     '', None),
])
def test_put_records(llc, dlc, snep_req, ndef_req, snep_rsp, result):
    llc.send.return_value = True
    llc.poll.return_value = True
    llc.recv.return_value = HEX(snep_rsp)
    assert nfc.snep.SnepClient(llc).put_records(ndef_req) == result
    llc.connect.assert_called_once_with(dlc, b'urn:nfc:sn:snep')
    llc.send.assert_called_once_with(dlc, HEX(snep_req), 0)
    llc.poll.assert_called_once_with(dlc, 'recv', 1.0)
    llc.recv.assert_called_once_with(dlc)
    llc.close.assert_called_once_with(dlc)


@pytest.mark.parametrize("kwargs, service_name", [
    ({}, b'urn:nfc:sn:snep'),
    ({'default_service_name': b'urn:nfc:sn:my-snep'}, b'urn:nfc:sn:my-snep'),
])
def test_with_context_manager(llc, dlc, kwargs, service_name):
    snep_req = HEX('10 01 00000007 00000400 d00000')
    snep_res = HEX('10 81 00000003 d00000')
    llc.send.return_value = True
    llc.poll.return_value = True
    llc.recv.return_value = snep_res
    with nfc.snep.SnepClient(llc, **kwargs) as client:
        client.get_octets() == HEX('d00000')
        client.get_octets() == HEX('d00000')
    llc.connect.assert_called_once_with(dlc, service_name)
    llc.send.assert_has_calls(2 * [mock.call(dlc, snep_req, 0)])
    llc.poll.assert_has_calls(2 * [mock.call(dlc, 'recv', 1.0)])
    llc.recv.assert_has_calls(2 * [mock.call(dlc)])
    llc.close.assert_called_once_with(dlc)
