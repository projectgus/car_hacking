#!/usr/bin/env python3
#
# KWP2000 script adapted from https://github.com/pd0wm/pq-flasher/blob/master/kwp2000.py
# Original Copyright (c) 2021 Willem Melching
# SPDX-License-Identifier: MIT
import struct
import sys
from enum import IntEnum

import can
from iso_session import Session


class NegativeResponseError(Exception):
    def __init__(self, message, service_id, error_code):
        super().__init__()
        self.message = message
        self.service_id = service_id
        self.error_code = error_code

    def __str__(self):
        return self.message


class InvalidServiceIdError(Exception):
    pass


class InvalidSubFunctionError(Exception):
    pass


class TimeoutError(RuntimeError):
    pass


class SERVICE_TYPE(IntEnum):
    DIAGNOSTIC_SESSION_CONTROL = 0x10
    ECU_RESET = 0x11
    READ_FREEZE_FRAME_DATA = 0x12
    READ_DIAGNOSTIC_TROUBLE_CODES = 0x13
    CLEAR_DIAGNOSTIC_INFORMATION = 0x14
    READ_STATUS_OF_DIAGNOSTIC_TROUBLE_CODES = 0x17
    READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS = 0x18
    READ_ECU_IDENTIFICATION = 0x1A
    STOP_DIAGNOSTIC_SESSION = 0x20
    READ_DATA_BY_LOCAL_IDENTIFIER = 0x21
    READ_DATA_BY_COMMON_IDENTIFIER = 0x22
    READ_MEMORY_BY_ADDRESS = 0x23
    SET_DATA_RATES = 0x26
    SECURITY_ACCESS = 0x27
    DYNAMICALLY_DEFINE_LOCAL_IDENTIFIER = 0x2C
    WRITE_DATA_BY_COMMON_IDENTIFIER = 0x2E
    INPUT_OUTPUT_CONTROL_BY_COMMON_IDENTIFIER = 0x2F
    INPUT_OUTPUT_CONTROL_BY_LOCAL_IDENTIFIER = 0x30
    START_ROUTINE_BY_LOCAL_IDENTIFIER = 0x31
    STOP_ROUTINE_BY_LOCAL_IDENTIFIER = 0x32
    REQUEST_ROUTINE_RESULTS_BY_LOCAL_IDENTIFIER = 0x33
    REQUEST_DOWNLOAD = 0x34
    REQUEST_UPLOAD = 0x35
    TRANSFER_DATA = 0x36
    REQUEST_TRANSFER_EXIT = 0x37
    START_ROUTINE_BY_ADDRESS = 0x38
    STOP_ROUTINE_BY_ADDRESS = 0x39
    REQUEST_ROUTINE_RESULTS_BY_ADDRESS = 0x3A
    WRITE_DATA_BY_LOCAL_IDENTIFIER = 0x3B
    WRITE_MEMORY_BY_ADDRESS = 0x3D
    TESTER_PRESENT = 0x3E
    ESC_CODE = 0x80
    STOP_COMMUNICATION = 0x82


class ROUTINE_CONTROL_TYPE(IntEnum):
    ERASE_FLASH = 0xC4
    CALCULATE_FLASH_CHECKSUM = 0xC5


class ECU_IDENTIFICATION_TYPE(IntEnum):
    ECU_IDENT = 0x9B
    STATUS_FLASH = 0x9C


class SESSION_TYPE(IntEnum):
    PROGRAMMING = 0x85
    ENGINEERING_MODE = 0x86
    DIAGNOSTIC = 0x89


class ACCESS_TYPE(IntEnum):
    PROGRAMMING_REQUEST_SEED = 1
    PROGRAMMING_SEND_KEY = 2
    REQUEST_SEED = 3
    SEND_KEY = 4


class COMPRESSION_TYPE(IntEnum):
    UNCOMPRESSED = 0x0


class ENCRYPTION_TYPE(IntEnum):
    UNENCRYPTED = 0x0


_negative_response_codes = {
    0x10: "generalReject",
    0x11: "serviceNotSupported",
    0x12: "subFunctionNotSupported-invalidFormat",
    0x21: "busy-RepeatRequest",
    0x22: "conditionsNotCorrect or requestSequenceError",
    0x23: "routineNotComplete",
    0x31: "requestOutOfRange",
    0x33: "securityAccessDenied",
    0x35: "invalidKey",
    0x36: "exceedNumberOfAttempts",
    0x37: "requiredTimeDelayNotExpired",
    0x40: "downloadNotAccepted",
    0x41: "improperDownloadType",
    0x42: "cantDownloadToSpecifiedAddress",
    0x43: "cantDownloadNumberOfBytesRequested",
    0x50: "uploadNotAccepted",
    0x51: "improperUploadType",
    0x52: "cantUploadFromSpecifiedAddress",
    0x53: "cantUploadNumberOfBytesRequested",
    0x71: "transferSuspended",
    0x72: "transferAborted",
    0x74: "illegalAddressInBlockTransfer",
    0x75: "illegalByteCountInBlockTransfer",
    0x76: "illegalBlockTransferType",
    0x77: "blockTransferDataChecksumError",
    0x78: "reqCorrectlyRcvd-RspPending(requestCorrectlyReceived-ResponsePending)",
    0x79: "incorrectByteCountDuringBlockTransfer",
}


class KWP2000Client:
    def __init__(self, transport: Session, debug: bool = False):
        self.transport = transport
        self.debug = debug

    def _kwp(
        self, service_type: SERVICE_TYPE, subfunction: int = None, data: bytes = None
    ) -> bytes:
        req = bytes([service_type])

        if subfunction is not None:
            req += bytes([subfunction])
        if data is not None:
            req += data

        if self.debug:
            print(f"KWP TX: {req.hex()}")

        with self.transport as t:
            resp = t.request(req)

        if resp is None:
            raise TimeoutError(f"No response to request {req.hex()}")

        if self.debug:
            print(f"KWP RX: {resp.hex() if resp else None}")

        resp_sid = resp[0] if resp else None

        # negative response
        if resp_sid == 0x7F:
            service_id = resp[1] if len(resp) > 1 else -1

            if service_id != service_type:
                raise InvalidServiceIdError(f"invalid negative response service id: {service_id:#x} - expected {service_type:#x}")

            try:
                service_desc = SERVICE_TYPE(service_id).name
            except BaseException:
                service_desc = "NON_STANDARD_SERVICE"

            error_code = resp[2] if len(resp) > 2 else -1

            try:
                error_desc = _negative_response_codes[error_code]
            except BaseException:
                error_desc = resp[2:].hex()

            raise NegativeResponseError(
                "{} - {}".format(service_desc, error_desc), service_id, error_code
            )

        # positive response
        if service_type + 0x40 != resp_sid:
            resp_sid_hex = hex(resp_sid) if resp_sid is not None else None
            raise InvalidServiceIdError(
                "invalid response service id: {}".format(resp_sid_hex)
            )

        # check subfunction
        if subfunction is not None:
            resp_sfn = resp[1] if len(resp) > 1 else None

            if subfunction != resp_sfn:
                resp_sfn_hex = hex(resp_sfn) if resp_sfn is not None else None
                raise InvalidSubFunctionError(
                    f"invalid response subfunction: {resp_sfn_hex:x}"
                )

        # return data (exclude service id and sub-function id)
        return resp[(1 if subfunction is None else 2):]

    def diagnostic_session_control(self, session_type: SESSION_TYPE):
        self._kwp(SERVICE_TYPE.DIAGNOSTIC_SESSION_CONTROL, subfunction=session_type)

    def read_diagnostic_trouble_codes(self):
        # There is an optional groupOfDTC parameter, but not bothering to pass it

        # TODO: decode result!
        return self._kwp(SERVICE_TYPE.READ_DIAGNOSTIC_TROUBLE_CODES)

    def read_status_of_diagnostic_trouble_codes(self):
        # TODO: decode result!
        #
        # on kona only txid 0x7a8 seems to see this packet, and doesn't seem to really respond?
        return self._kwp(
            SERVICE_TYPE.READ_STATUS_OF_DIAGNOSTIC_TROUBLE_CODES, data=b"\x00\x00"
        )

    def read_diagnostic_trouble_codes_by_status(self, status: int):
        # TODO: decode result!
        return self._kwp(
            SERVICE_TYPE.READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS, data=b"\x00\x80\x00"
        )  # 008000, 20ff00, 60ff00, 004000  also work on Kona

    def security_access(self, access_type: ACCESS_TYPE, security_key: bytes = b""):
        request_seed = access_type % 2 != 0

        if request_seed and len(security_key) != 0:
            raise ValueError("security_key not allowed")
        if not request_seed and len(security_key) == 0:
            raise ValueError("security_key is missing")

        return self._kwp(
            SERVICE_TYPE.SECURITY_ACCESS, subfunction=access_type, data=security_key
        )

    def read_ecu_identifcation(self, data_identifier_type: ECU_IDENTIFICATION_TYPE):
        return self._kwp(SERVICE_TYPE.READ_ECU_IDENTIFICATION, data_identifier_type)

    def request_download(
        self,
        memory_address: int,
        uncompressed_size: int,
        compression_type: COMPRESSION_TYPE = COMPRESSION_TYPE.UNCOMPRESSED,
        encryption_type: ENCRYPTION_TYPE = ENCRYPTION_TYPE.UNENCRYPTED,
    ):
        if memory_address > 0xFFFFFF:
            raise ValueError(f"invalid memory_address {memory_address}")
        if uncompressed_size > 0xFFFFFF:
            raise ValueError(f"invalid uncompressed_size {uncompressed_size}")

        addr = struct.pack(">L", memory_address)[1:]
        size = struct.pack(">L", uncompressed_size)[1:]
        data = addr + bytes([(compression_type << 4) | encryption_type]) + size
        ret = self._kwp(SERVICE_TYPE.REQUEST_DOWNLOAD, subfunction=None, data=data)
        if len(ret) == 1:
            return struct.unpack(">B", ret)[0]
        elif len(ret) == 2:
            return struct.unpack(">H", ret)[0]
        else:
            raise ValueError(f"Invalid response {ret.hex()}")

    def start_routine_by_local_identifier(
        self, routine_control: ROUTINE_CONTROL_TYPE, data: bytes
    ) -> bytes:
        return self._kwp(
            SERVICE_TYPE.START_ROUTINE_BY_LOCAL_IDENTIFIER, routine_control, data
        )

    def request_routine_results_by_local_identifier(
        self, routine_control: ROUTINE_CONTROL_TYPE
    ) -> bytes:
        return self._kwp(
            SERVICE_TYPE.REQUEST_ROUTINE_RESULTS_BY_LOCAL_IDENTIFIER, routine_control
        )

    def erase_flash(self, start_address: int, end_address: int) -> bytes:
        if start_address > 0xFFFFFF:
            raise ValueError(f"invalid start_address {start_address}")
        if end_address > 0xFFFFFF:
            raise ValueError(f"invalid end_address {end_address}")

        start = struct.pack(">L", start_address)[1:]
        end = struct.pack(">L", end_address)[1:]
        return self.start_routine_by_local_identifier(
            ROUTINE_CONTROL_TYPE.ERASE_FLASH, start + end
        )

    def calculate_flash_checksum(
        self, start_address: int, end_address: int, checksum: int
    ) -> bytes:
        if start_address > 0xFFFFFF:
            raise ValueError(f"invalid start_address {start_address}")
        if end_address > 0xFFFFFF:
            raise ValueError(f"invalid end_address {end_address}")
        if checksum > 0xFFFF:
            raise ValueError(f"invalid checksum {checksum}")

        start = struct.pack(">L", start_address)[1:]
        end = struct.pack(">L", end_address)[1:]
        chk = struct.pack(">H", checksum)
        return self.start_routine_by_local_identifier(
            ROUTINE_CONTROL_TYPE.CALCULATE_FLASH_CHECKSUM, start + end + chk
        )

    def transfer_data(self, data: bytes) -> bytes:
        return self._kwp(SERVICE_TYPE.TRANSFER_DATA, data=data)

    def request_transfer_exit(self) -> bytes:
        return self._kwp(SERVICE_TYPE.REQUEST_TRANSFER_EXIT)

    def stop_communication(self) -> bytes:
        return self._kwp(SERVICE_TYPE.STOP_COMMUNICATION)


def main(bus, txid, debug=True):
    rxid = txid + 8
    if debug:
        print("TXID {:#x} RXID {:#x}".format(txid, rxid))
    tp = Session(bus, txid, rxid)

    kwp_client = KWP2000Client(tp, debug=debug)

    kwp_client._kwp(SERVICE_TYPE.ECU_RESET, 0x02)

    # seems happy with 0x81 ("Default Session" and 0x90 ("ECU Passive Session")
    kwp_client.diagnostic_session_control(0x81)

    # ident = kwp_client.read_ecu_identifcation(ECU_IDENTIFICATION_TYPE.ECU_IDENT)
    # print(f"Part Number {ident[:10]}")

    for d in range(0xFFFF + 1):
        kwp_client.diagnostic_session_control(0x81)
        try:
            resp = kwp_client._kwp(0x17, data=struct.pack("<H", d))
            print(f"OK! d={d:#x}, {resp.hex()}")
        except Exception as e:
            if "invalidFormat" not in str(e):
                print(e)
    print("Done?")

    try:
        resp = kwp_client.read_diagnostic_trouble_codes_by_status(0x80)
        print(resp.hex())
    except Exception as e:
        print(e)

    try:
        resp = kwp_client.read_diagnostic_trouble_codes()
        print(resp.hex())
    except Exception as e:
        print(e)

    try:
        resp = kwp_client.read_status_of_diagnostic_trouble_codes()
        print(resp.hex())
    except Exception as e:
        print(e)

    # status = kwp_client.read_ecu_identifcation(ECU_IDENTIFICATION_TYPE.STATUS_FLASH)
    # print("Flash status", status)


if __name__ == "__main__":
    bus = can.Bus()
    debug = True
    main(bus, int(sys.argv[1], 0), debug)
