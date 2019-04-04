# -*- coding: latin-1 -*-
# -----------------------------------------------------------------------------
# Copyright 2011, 2017 Stephen Tiedemann <stephen.tiedemann@gmail.com>
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
"""Device driver for the Arygon ACR122U contactless reader.

The Arygon ACR122U is a PC/SC compliant contactless reader that
connects via USB and uses the USB CCID profile. It is normally
intented to be used with a PC/SC stack but this driver interfaces
directly with the inbuilt PN532 chipset by tunneling commands through
the PC/SC Escape command. The driver is limited in functionality
because the embedded microprocessor (that implements the PC/SC stack)
also operates the PN532; it does not allow all commands to pass as
desired and reacts on chip responses with its own (legitimate)
interpretation of state.

==========  =======  ============
function    support  remarks
==========  =======  ============
sense_tta   yes      Type 1 (Topaz) Tags are not supported
sense_ttb   yes      ATTRIB by firmware voided with S(DESELECT)
sense_ttf   yes
sense_dep   yes
listen_tta  no
listen_ttb  no
listen_ttf  no
listen_dep  no
==========  =======  ============

"""
import errno
import logging
import os
import struct
from typing import Union

import nfc.clf
from nfc.clf.transport import USB
from . import pn532

log = logging.getLogger(__name__)


def init(transport):
    device = Device(Chipset(transport))
    device._vendor_name = transport.manufacturer_name
    device._device_name = transport.product_name.split()[0]
    return device


class Device(pn532.Device):
    # Device driver class for the ACR122U.

    def __init__(self, chipset):
        super(Device, self).__init__(chipset, logger=log)

    def sense_tta(self, target: nfc.clf.RemoteTarget):
        """Activate the RF field and probe for a Type A Target at 106
        kbps. Other bitrates are not supported. Type 1 Tags are not
        supported because the device does not allow to send the
        correct RID command (even though the PN532 does).

        """
        return super(Device, self).sense_tta(target)

    def sense_ttb(self, target: nfc.clf.RemoteTarget):
        """Activate the RF field and probe for a Type B Target.

        The RC-S956 can discover Type B Targets (Type 4B Tag) at 106
        kbps. For a Type 4B Tag the firmware automatically sends an
        ATTRIB command that configures the use of DID and 64 byte
        maximum frame size. The driver reverts this configuration with
        a DESELECT and WUPB command to return the target prepared for
        activation (which nfcpy does in the tag activation code).

        """
        return super(Device, self).sense_ttb(target)

    def sense_ttf(self, target: nfc.clf.RemoteTarget):
        """Activate the RF field and probe for a Type F Target. Bitrates 212
        and 424 kpbs are supported.

        """
        return super(Device, self).sense_ttf(target)

    def sense_dep(self, target: nfc.clf.RemoteTarget):
        """Search for a DEP Target. Both passive and passive communication
        mode are supported.

        """
        return super(Device, self).sense_dep(target)

    def listen_tta(self, target: nfc.clf.RemoteTarget, timeout):
        """Listen as Type A Target is not supported."""
        info = "{device} does not support listen as Type A Target"
        raise nfc.clf.UnsupportedTargetError(info.format(device=self))

    def listen_ttb(self, target: nfc.clf.RemoteTarget, timeout):
        """Listen as Type B Target is not supported."""
        info = "{device} does not support listen as Type B Target"
        raise nfc.clf.UnsupportedTargetError(info.format(device=self))

    def listen_ttf(self, target: nfc.clf.RemoteTarget, timeout):
        """Listen as Type F Target is not supported."""
        info = "{device} does not support listen as Type F Target"
        raise nfc.clf.UnsupportedTargetError(info.format(device=self))

    def listen_dep(self, target: nfc.clf.RemoteTarget, timeout):
        """Listen as DEP Target is not supported."""
        info = "{device} does not support listen as DEP Target"
        raise nfc.clf.UnsupportedTargetError(info.format(device=self))

    def turn_on_led_and_buzzer(self):
        """Buzz and turn red."""
        self.chipset.set_buzzer_and_led_to_active()

    def turn_off_led_and_buzzer(self):
        """Back to green."""
        self.chipset.set_buzzer_and_led_to_default()


class Chipset(pn532.Chipset):
    # Maximum size of a host command frame to the contactless chip.
    host_command_frame_max_size = 254

    # Supported BrTy (baud rate / modulation type) values for the
    # InListPassiveTarget command. Corresponds to 106 kbps Type A, 212
    # kbps Type F, 424 kbps Type F, and 106 kbps Type B. The value for
    # 106 kbps Innovision Jewel Tag (although supported by PN532) is
    # removed because the RID command can not be send.
    in_list_passive_target_brty_range = (0, 1, 2, 3)

    def __init__(self, transport: USB):
        self.transport = transport

        # read ACR122U firmware version string
        reader_version = self.ccid_xfr_block(bytearray.fromhex("FF00480000"))  # type: bytes
        if not reader_version.startswith(b"ACR122U"):
            log.error("failed to retrieve ACR122U version string")
            raise IOError(errno.ENODEV, os.strerror(errno.ENODEV))

        if int(chr(reader_version[7])) < 2:
            log.error("{0} not supported, need 2.x".format(reader_version[7:]))
            raise IOError(errno.ENODEV, os.strerror(errno.ENODEV))

        log.debug("initialize " + str(reader_version))

        # set icc power on
        log.debug("CCID ICC-POWER-ON")
        frame = bytearray.fromhex("62000000000000000000")
        transport.write(frame)
        transport.read(100)

        # disable autodetection
        log.debug("Set PICC Operating Parameters")
        self.ccid_xfr_block(bytearray.fromhex("FF00517F00"))

        # switch red/green led off/on
        log.debug("Configure Buzzer and LED")
        self.set_buzzer_and_led_to_default()

        super(Chipset, self).__init__(transport, logger=log)

    def close(self):
        self.ccid_xfr_block(bytearray.fromhex("FF00400C0400000000"))
        self.transport.close()
        self.transport = None

    def set_buzzer_and_led_manually(self,
                                    led_state_control: int,
                                    t1_dur: float, t2_dur: float,
                                    reps: int, buzz_link: int):
        """
        Control the buzzer and LEDs.

        Durations are number of seconds as a float. Internally it must be in multiples of 100ms.
        """

        if type(t1_dur) is float:
            t1_dur = int(t1_dur * 10)  # convert to unit of "100s of milliseconds"
        if type(t2_dur) is float:
            t2_dur = int(t2_dur * 10)  # convert to unit of "100s of milliseconds"

        data = bytearray([
            0xFF, 0x00, 0x40, led_state_control, 0x04,
            t1_dur, t2_dur, reps, buzz_link
        ])

        total_timeout = 0.1 * reps * (t1_dur + t2_dur)

        self.ccid_xfr_block(data, timeout=total_timeout)

    def set_buzzer_manually(self, t1_dur: float, t2_dur: float, reps: int, buzz_link: int):
        self.set_buzzer_and_led_manually(0, t1_dur, t2_dur, reps, buzz_link)

    def set_buzzer_and_led_to_default(self):
        """Turn off buzzer and set LED to default (green only). """
        # bytearray.fromhex("FF00400E0400000000")
        self.set_buzzer_and_led_manually(0x0E, 0x00, 0x00, 0x00, 0x00)

    def set_buzzer_and_led_to_active(self, duration_in_ms=300):
        """Turn on buzzer and set LED to red only. The timeout here must exceed
         the total buzzer/flash duration defined in bytes 5-8. """
        duration_in_tenths_of_second = min(duration_in_ms / 100, 255)
        timeout_in_seconds = (duration_in_tenths_of_second + 1) / 10.0
        data = "FF00400D04{:02X}000101".format(int(duration_in_tenths_of_second))

        self.set_buzzer_and_led_manually(0x0D, int(duration_in_tenths_of_second), 0, 0x01, 0x01)

        self.ccid_xfr_block(data, timeout=timeout_in_seconds)

    def send_ack(self):
        # Send an ACK frame, usually to terminate most recent command.
        self.ccid_xfr_block(Chipset.ACK)

    def ccid_xfr_block(self, data: bytearray, timeout: float = 0.1):
        """Encapsulate host command *data* into an PC/SC Escape command to
        send to the device and extract the chip response if received
        within *timeout* seconds.

        """
        frame = struct.pack("<BI5B", 0x6F, len(data), 0, 0, 0, 0, 0) + data
        self.transport.write(bytearray(frame))
        frame = self.transport.read(int(timeout * 1000))
        if not frame or len(frame) < 10:
            log.error("insufficient data for decoding ccid response")
            raise IOError(errno.EIO, os.strerror(errno.EIO))
        if frame[0] != 0x80:
            log.error("expected a RDR_to_PC_DataBlock")
            raise IOError(errno.EIO, os.strerror(errno.EIO))
        # if len(frame) != 10 + struct.unpack("<I", buffer(frame, 1, 4))[0]:
        if len(frame) != 10 + struct.unpack("<I", frame[1:5])[0]:
            log.error("RDR_to_PC_DataBlock length mismatch")
            raise IOError(errno.EIO, os.strerror(errno.EIO))
        return frame[10:]

    def command(self, cmd_code: int, cmd_data: Union[str, bytes], timeout: float):
        """Send a host command and return the chip response.

        """
        if type(cmd_data) is str:
            cmd_data = bytes(cmd_data, 'UTF-8')

        log.log(logging.DEBUG-1, "%s %s", self.CMD[cmd_code], cmd_data.hex())

        frame_out = bytearray([0xD4, cmd_code]) + cmd_data
        frame_out = bytearray([0xFF, 0x00, 0x00, 0x00, len(frame_out)]) + frame_out

        frame_in = self.ccid_xfr_block(frame_out, timeout)
        if not frame_in or len(frame_in) < 4:
            log.error("insufficient data for decoding chip response")
            raise IOError(errno.EIO, os.strerror(errno.EIO))
        if not (frame_in[0] == 0xD5 and frame_in[1] == cmd_code + 1):
            log.error("received invalid chip response")
            raise IOError(errno.EIO, os.strerror(errno.EIO))
        if not (frame_in[-2] == 0x90 and frame_in[-1] == 0x00):
            log.error("received pseudo apdu with error status")
            raise IOError(errno.EIO, os.strerror(errno.EIO))
        return frame_in[2:-2]
