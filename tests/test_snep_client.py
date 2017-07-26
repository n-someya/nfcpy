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


@pytest.fixture
def dlc():
    return nfc.llcp.tco.DataLinkConnection(128, 10)


@pytest.fixture
def llc(dlc):
    llc = mock.create_autospec(nfc.llcp.llc.LogicalLinkController)
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
    (HEX('10 01 00000007 00000400 d00000'), None,
     HEX('10 81 00000003 d00000'), [ndef.Record()]),
    (HEX('10 01 0000000c 00000400 d101045402656e61'), [ndef.TextRecord('a')],
     HEX('10 81 00000008 d101045402656e62'), [ndef.TextRecord('b')]),
    (HEX('10 01 00000007 00000400 d00000'), [ndef.Record()],
     HEX('10 81 00000000'), []),
    (HEX('10 01 00000007 00000400 d00000'), [ndef.Record()],
     HEX('10 81 00000001 00'), []),
    (HEX('10 01 00000007 00000400 d00000'), [ndef.Record()],
     HEX(''), []),
])
def test_get_records(llc, dlc, snep_req, ndef_req, snep_rsp, ndef_rsp):
    llc.getsockopt.return_value = 128
    llc.send.return_value = True
    llc.poll.return_value = True
    llc.recv.return_value = snep_rsp
    assert nfc.snep.SnepClient(llc).get_records(ndef_req) == ndef_rsp
    llc.connect.assert_called_once_with(dlc, b'urn:nfc:sn:snep')
    llc.getsockopt.assert_called_once_with(dlc, nfc.llcp.SO_SNDMIU)
    llc.send.assert_called_once_with(dlc, snep_req, 0)
    llc.poll.assert_called_once_with(dlc, 'recv', 1.0)
    llc.recv.assert_called_once_with(dlc)
    llc.close.assert_called_once_with(dlc)


@pytest.mark.parametrize("snep_req, ndef_req, snep_rsp, result", [
    (HEX('10 02 00000003 d00000'), [ndef.Record()],
     HEX('10 81 00000000'), True),
    (HEX('10 02 00000008 d101045402656e61'), [ndef.TextRecord('a')],
     HEX('10 81 00000000'), True),
    (HEX('10 02 00000008 d101045402656e61'), [ndef.TextRecord('a')],
     HEX(''), False),
])
def test_put_records(llc, dlc, snep_req, ndef_req, snep_rsp, result):
    llc.getsockopt.return_value = 128
    llc.send.return_value = True
    llc.poll.return_value = True
    llc.recv.return_value = snep_rsp
    assert nfc.snep.SnepClient(llc).put_records(ndef_req) == result
    llc.connect.assert_called_once_with(dlc, b'urn:nfc:sn:snep')
    llc.getsockopt.assert_called_once_with(dlc, nfc.llcp.SO_SNDMIU)
    llc.send.assert_called_once_with(dlc, snep_req, 0)
    llc.poll.assert_called_once_with(dlc, 'recv', 1.0)
    llc.recv.assert_called_once_with(dlc)
    llc.close.assert_called_once_with(dlc)


@pytest.mark.parametrize("kwargs, service_name", [
    ({}, b'urn:nfc:sn:snep'),
    ({'default_service_name': b'urn:nfc:sn:my-snep'}, b'urn:nfc:sn:my-snep'),
])
def test_with_context_manager(llc, dlc, kwargs, service_name):
    llc.getsockopt.return_value = 128
    llc.send.return_value = True
    llc.poll.return_value = True
    llc.recv.side_effect = [
        HEX('10 81 00000003 d00000'),
        HEX('10 81 00000000'),
    ]
    with nfc.snep.SnepClient(llc, **kwargs) as client:
        assert client.get_octets() == HEX('d00000')
        assert client.put_octets(HEX('d00000')) is True
    llc.connect.assert_called_once_with(dlc, service_name)
    llc.getsockopt.assert_called_once_with(dlc, nfc.llcp.SO_SNDMIU)
    llc.send.assert_has_calls([
        mock.call(dlc, HEX('10 01 00000007 00000400 d00000'), 0),
        mock.call(dlc, HEX('10 02 00000003 d00000'), 0),
    ])
    llc.poll.assert_has_calls(2 * [mock.call(dlc, 'recv', 1.0)])
    llc.recv.assert_has_calls(2 * [mock.call(dlc)])
    llc.close.assert_called_once_with(dlc)


@pytest.mark.parametrize("method", [
    'nfc.snep.SnepClient(llc).get_octets()',
    'nfc.snep.SnepClient(llc).put_octets(b"d00000")',
])
def test_connect_refused(llc, dlc, method):
    llc.connect.side_effect = nfc.llcp.ConnectRefused(1)
    assert bool(eval(method)) is False
    llc.connect.assert_called_once_with(dlc, b'urn:nfc:sn:snep')
    llc.close.assert_not_called()


@pytest.mark.parametrize("method_call, snep_req, snep_rsp, errno, errstr", [
    ("get_octets()",
     HEX('10 01 00000007 00000400 d00000'),
     HEX('10 C0 00000003 d00000'),
     192, "resource not found"),
    ("get_octets()",
     HEX('10 01 00000007 00000400 d00000'),
     HEX('10 C1 00000003 d00000'),
     193, "resource exceeds data size limit"),
    ("get_octets()",
     HEX('10 01 00000007 00000400 d00000'),
     HEX('10 C2 00000003 d00000'),
     194, "malformed request not understood"),
    ("get_octets()",
     HEX('10 01 00000007 00000400 d00000'),
     HEX('10 E0 00000003 d00000'),
     224, "unsupported functionality requested"),
    ("put_octets(b'\\xd0\\x00\\x00')",
     HEX('10 02 00000003 d00000'),
     HEX('10 E1 00000000'),
     225, "unsupported protocol version"),
])
def test_snep_error(llc, dlc, method_call, snep_req, snep_rsp, errno, errstr):
    llc.getsockopt.return_value = 128
    llc.send.return_value = True
    llc.poll.return_value = True
    llc.recv.return_value = snep_rsp
    with pytest.raises(nfc.snep.SnepError) as excinfo:
        eval("nfc.snep.SnepClient(llc)." + method_call)
    assert errstr in str(excinfo.value)
    assert excinfo.value.errno == errno
    llc.connect.assert_called_once_with(dlc, b'urn:nfc:sn:snep')
    llc.getsockopt.assert_called_once_with(dlc, nfc.llcp.SO_SNDMIU)
    llc.send.assert_called_once_with(dlc, snep_req, 0)
    llc.poll.assert_called_once_with(dlc, 'recv', 1.0)
    llc.recv.assert_called_once_with(dlc)
    llc.close.assert_called_once_with(dlc)


@pytest.mark.parametrize("recv, send, success", [
    ([HEX('10 80 00000000'), HEX('10 81 00000000')],
     [HEX('10 02 00000003 d000'), HEX('00')], True),
    ([HEX('10 ff 00000000')],
     [HEX('10 02 00000003 d000')], False),
])
def test_send_after_continue(llc, dlc, recv, send, success):
    llc.getsockopt.return_value = 8
    llc.poll.return_value = True
    llc.send.return_value = True
    llc.recv.side_effect = recv
    assert nfc.snep.SnepClient(llc).put_octets(HEX('d00000')) is success
    llc.send.assert_has_calls([mock.call(dlc, data, 0) for data in send])


@pytest.mark.parametrize("send_success, send_data", [
    ([True, False], [HEX('10 01 00000007 0000'), HEX('0400 d00000')]),
    ([False], [HEX('10 01 00000007 0000')]),
])
def test_get_fail_to_send(llc, dlc, send_success, send_data):
    llc.getsockopt.return_value = 8
    llc.poll.return_value = True
    llc.send.side_effect = send_success
    llc.recv.side_effect = [HEX('10 80 00000000'), HEX('10 81 00000003d00000')]
    assert nfc.snep.SnepClient(llc).get_octets() is b''
    llc.send.assert_has_calls([mock.call(dlc, data, 0) for data in send_data])


@pytest.mark.parametrize("send_success, send_data", [
    ([True, False], [HEX('10 02 00000003 d000'), HEX('00')]),
    ([False], [HEX('10 02 00000003 d000')]),
])
def test_put_fail_to_send(llc, dlc, send_success, send_data):
    llc.getsockopt.return_value = 8
    llc.poll.return_value = True
    llc.send.side_effect = send_success
    llc.recv.side_effect = [HEX('10 80 00000000'), HEX('10 81 00000000')]
    assert nfc.snep.SnepClient(llc).put_octets(HEX('d00000')) is False
    llc.send.assert_has_calls([mock.call(dlc, data, 0) for data in send_data])


@pytest.mark.parametrize("recv, send, result", [
    ([HEX('10 81 00000008'), HEX('d101045402656e61')],
     [HEX('10 01 00000007 00000400 d00000'), HEX('10 00 00000000')],
     HEX('d101045402656e61')),
])
def test_recv_after_continue(llc, dlc, recv, send, result):
    llc.getsockopt.return_value = 128
    llc.poll.return_value = True
    llc.send.return_value = True
    llc.recv.side_effect = recv
    assert nfc.snep.SnepClient(llc).get_octets() == result
    print(llc.send.mock_calls)
    llc.send.assert_has_calls([mock.call(dlc, data, 0) for data in send])


@pytest.mark.parametrize("poll_success, send_data", [
    ([True, False], [HEX('10010000000700000400d00000'), HEX('100000000000')]),
    ([False], [HEX('10010000000700000400d00000')]),
])
def test_get_fail_to_recv(llc, dlc, poll_success, send_data):
    llc.getsockopt.return_value = 128
    llc.send.return_value = True
    llc.poll.side_effect = poll_success
    llc.recv.side_effect = [HEX('10 81 00000008'), HEX('d101045402656e61')]
    assert nfc.snep.SnepClient(llc).get_octets() is b''
    print(llc.send.mock_calls)
    llc.send.assert_has_calls([mock.call(dlc, data, 0) for data in send_data])


def test_get_acceptable_length_exceeded(llc, dlc):
    llc.getsockopt.return_value = 128
    llc.send.return_value = True
    llc.poll.return_value = True
    llc.recv.side_effect = [HEX('10 81 10000000')]
    assert nfc.snep.SnepClient(llc).get_octets() is b''
    print(llc.send.mock_calls)
    llc.send.assert_called_once_with(dlc, HEX('10010000000700000400d00000'), 0)
