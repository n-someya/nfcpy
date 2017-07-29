# -*- coding: latin-1 -*-
# -----------------------------------------------------------------------------
# Copyright 2009, 2017 Stephen Tiedemann <stephen.tiedemann@gmail.com>
#
# Licensed under the EUPL, Version 1.1 or - as soon they
# will be approved by the European Commission - subsequent
# versions of the EUPL (the "Licence");
# You may not use this work except in compliance with the
# Licence.
# You may obtain a copy of the Licence at:
#
# https://joinup.ec.europa.eu/software/page/eupl
#
# Unless required by applicable law or agreed to in
# writing, software distributed under the Licence is
# distributed on an "AS IS" basis,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied.
# See the Licence for the specific language governing
# permissions and limitations under the Licence.
# -----------------------------------------------------------------------------
#
# Simple NDEF Exchange Protocol (SNEP) - Server Base Class
#
from threading import Thread
from struct import pack, unpack
from binascii import hexlify

import nfc.llcp
import nfc.ndef
import ndef

import logging
log = logging.getLogger(__name__)


class SnepServer(Thread):
    """ NFC Forum Simple NDEF Exchange Protocol server
    """
    def __init__(self, llc, **kwargs):
        max_acceptable_length = kwargs.get('max_acceptable_length', 0x100000)
        service_name = kwargs.get('service_name', b'urn:nfc:sn:snep')
        recv_miu = kwargs.get('recv_miu', 1984)
        recv_buf = kwargs.get('recv_buf', 15)

        if not hasattr(self, 'get_records'):
            self.get_records = self._get_records
        if not hasattr(self, 'put_records'):
            self.put_records = self._put_records
        if not hasattr(self, 'get_octets'):
            self.get_octets = self._get_octets
        if not hasattr(self, 'put_octets'):
            self.put_octets = self._put_octets
        self.set_callback(**kwargs)

        self.max_acceptable_length = min(max_acceptable_length, 0xFFFFFFFF)
        socket = nfc.llcp.Socket(llc, nfc.llcp.DATA_LINK_CONNECTION)
        recv_miu = socket.setsockopt(nfc.llcp.SO_RCVMIU, recv_miu)
        recv_buf = socket.setsockopt(nfc.llcp.SO_RCVBUF, recv_buf)
        socket.bind(service_name)
        socket.listen(backlog=2)
        Thread.__init__(self, target=self._listen, args=(socket,))

        log.info("snep server bound to port {0} (MIU={1}, RW={2}) "
                 "will accept up to {3} byte NDEF messages"
                 .format(socket.getsockname(), recv_miu, recv_buf,
                         self.max_acceptable_length))

    def set_callback(self, **kwargs):
        self.get_records = kwargs.get('get_records', self.get_records)
        self.put_records = kwargs.get('put_records', self.put_records)
        self.get_octets = kwargs.get('get_octets', self.get_octets)
        self.put_octets = kwargs.get('put_octets', self.put_octets)
        return self

    def _listen(self, socket):
        try:
            while True:
                client_socket = socket.accept()
                Thread(target=self._serve, args=(client_socket,)).start()
        except nfc.llcp.Error as e:
            (log.debug if e.errno == nfc.llcp.errno.EPIPE else log.error)(e)
        finally:
            socket.close()

    def _serve(self, socket):
        peer_sap = socket.getpeername()
        log.info("serving snep client on remote sap {0}".format(peer_sap))
        send_miu = socket.getsockopt(nfc.llcp.SO_SNDMIU)
        try:
            while True:
                snep_request = socket.recv()
                if not snep_request:
                    return  # connection closed

                if len(snep_request) < 6:
                    log.debug("snep msg initial fragment too short")
                    return  # bail out, this is a bad client

                version, opcode, length = unpack(">BBL", snep_request[:6])
                if (version >> 4) > 1:
                    log.debug("unsupported version {0}".format(version >> 4))
                    socket.send(b"\x10\xE1\x00\x00\x00\x00")
                    continue

                if length > self.max_acceptable_length:
                    log.debug("snep msg exceeds max acceptable length")
                    socket.send(b"\x10\xFF\x00\x00\x00\x00")
                    continue

                if len(snep_request) - 6 < length:
                    # request remaining fragments
                    socket.send(b"\x10\x80\x00\x00\x00\x00")
                    try:
                        while len(snep_request) - 6 < length:
                            snep_request += socket.recv()
                    except TypeError:
                        return  # received None -> connection closed

                # message complete, now handle the request
                if opcode == 1 and len(snep_request) >= 10:
                    snep_response = self._get_request(snep_request)
                elif opcode == 2:
                    snep_response = self._put_request(snep_request)
                else:
                    log.debug("bad request {0}".format(version & 0x0f))
                    snep_response = b"\x10\xC2\x00\x00\x00\x00"

                # send the snep response, fragment if needed
                if len(snep_response) <= send_miu:
                    socket.send(snep_response)
                else:
                    socket.send(snep_response[0:send_miu])
                    if socket.recv() == b"\x10\x00\x00\x00\x00\x00":
                        parts = range(send_miu, len(snep_response), send_miu)
                        for offset in parts:
                            fragment = snep_response[offset:offset+send_miu]
                            socket.send(fragment)

        except nfc.llcp.Error as e:
            (log.debug if e.errno == nfc.llcp.errno.EPIPE else log.error)(e)
        finally:
            socket.close()

    def _get_request(self, snep_request):
        acceptable_length = unpack(">L", snep_request[6:10])[0]
        try:
            rsp_octets = self.get_octets(acceptable_length, snep_request[10:])
            if len(rsp_octets) > acceptable_length:
                raise nfc.snep.SnepError(0xC1)
        except nfc.snep.SnepError as error:
            return pack('BBxxxx', 0x10, error.errno)
        else:
            return pack('>BBL', 0x10, 0x81, len(rsp_octets)) + rsp_octets

    def _get_octets(self, acceptable_length, request_octets):
        log.debug("SNEP GET {0}".format(hexlify(request_octets)))
        try:
            req_records = list(ndef.message_decoder(request_octets))
            rsp_records = self.get_records(req_records)
        except ndef.DecodeError as error:
            log.error(error)
            raise nfc.snep.SnepError(0xC2)
        else:
            return b''.join(ndef.message_encoder(rsp_records))

    def _get_records(self, request_records):
        raise nfc.snep.SnepError(0xE0)

    def _put_request(self, snep_request):
        try:
            self.put_octets(snep_request[6:])
        except nfc.snep.SnepError as error:
            return pack('BBxxxx', 0x10, error.errno)
        else:
            return pack('>BBxxxx', 0x10, 0x81)

    def _put_octets(self, request_octets):
        log.debug("SNEP PUT {0}".format(hexlify(request_octets)))
        try:
            req_records = list(ndef.message_decoder(request_octets))
            self.put_records(req_records)
        except ndef.DecodeError as error:
            log.error(error)
            raise nfc.snep.SnepError(0xC2)

    def _put_records(self, request_records):
        return
