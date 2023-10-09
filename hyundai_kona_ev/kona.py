import kwp2000
import struct
import time

KNOWN_TXIDS = [
    # Tuples of (TXID, "Name if known")

    # all of these at minimum respond to tester present!

    # Note: this list does not yet include VESS or active air flap, assume these
    # have diagnostic interfaces

    # some names are from "Kona PIDs" spreadsheet at
    # https://docs.google.com/spreadsheets/d/1-9jZafV9eZeBUnPQo7qQHbX2-_4qZfWfRVpidoF1owA/edit#gid=660740603
    #
    # and ones with "?" are from Kia e-Niro at
    # https://docs.google.com/spreadsheets/d/1eT2R8hmsD1hC__9LtnkZ3eDjLcdib9JR-3Myc97jy8M/edit#gid=587742707

    (0x725, '?725'),  # always available, No READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS
    (0x733, '?733'),  # not available in Off(awake), responds to tester present
    (0x770, 'IGMP'),  # always available, No READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS
    (0x776, '?776'),  # always available, responds to tester present
    (0x780, '?780'),  # always available
    (0x783, '?783'),  # always available
    (0x796, '?796'),  # not available in Off(awake)
    (0x7a0, 'BCM'),   # always available
    (0x7a5, 'SMK?'),  # always available, No READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS
    (0x7b3, 'AC'),    # not available in Off(awake), No READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS
    (0x7b6, '?7b6?'),  # always available
    (0x7b7, 'BSD?'),  # not available in Off(awake), No READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS, , blind spot detector (maybe)
    (0x7c4, 'MFC'),  # not available in Off(Awake), multi-function camera (maybe)
    (0x7c6, 'Cluster'),  # always available, no diagnostic session response, tester present is OK
    (0x7d1, 'ABS ESP'),  # always available, aka IEB module
    (0x7d2, '?7d2'),  # not available in Off(Awake)
    (0x7d4, 'speed?'),  # not available in Off(Awake), unit is named "speed" in Kona PIDs spreadsheet???
    (0x7e2, 'VCU'),  # always available, READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS(3 bytes) works
    (0x7e3, 'MCU'),  # not available in Off(Awake), READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS(3 bytes) works
    (0x7e4, 'BMU'),  # alwaus available, no diagnostic session response, UDS DTC service works
    (0x7e5, 'OBC'),  # not available in OFf(Awake), READ_DIAGNOSTIC_TROUBLE_CODES_BY_STATUS(3 bytes) works
    (0x7f1, '?7f1'),  # not available in Off(Awake)
]


def enumerate_services(bus, txid, debug=False):
    """Enumerate the possible ISO-15765 based services (UDS or KWP2000 or
    vendor) on a particular diagnostic CAN ID, by sending single byte
    service requests and recording all of the responses that aren't timeouts
    or standard "serviceNotSupported" errors.

    Service names are printed for KWP2000 services, not for UDS ones.

    Note there is some risk here of the car doing something unexpected in response
    to one of those, although most of them will be invalid requests as we don't pass any
    data arguments at all.

    It's also not clear if some ECUs will mask available services if they're not
    in the correct security access mode.
    """
    rxid = txid + 8
    tp = kwp2000.Session(bus, txid, rxid)
    kwp = kwp2000.KWP2000Client(tp, debug=debug)

    result = []

    for service_id in range(0x100):
        if service_id & 0x40:
            continue  # is a response ID

        try:
            service_desc = kwp2000.SERVICE_TYPE(service_id).name
        except BaseException:
            service_desc = "NON_STANDARD_SERVICE"

        if txid == 0x796 and service_id == 0x23:
            # In response to this request, this ECU sends an error response
            # [0x3, 0x7f, 0x23, 0x78] (reqCorrectlyRcvd-RspPending) every 5 seconds
            # and then seems to keep doing it forever. As if it gets stuck!
            print('0x23: Skipping known-weird service_id')
            result += [0x23]
            continue

        retries = 4
        while retries > 0:
            try:
                kwp._kwp(service_id)
                print(f"{service_id:#x}: {service_desc}: Success")
                result.append(service_id)
                retries = 0
            except kwp2000.NegativeResponseError as e:
                if "busy-RepeatRequest" in e.message:
                    # retry as requested
                    print(f'{service_id:#x} repeating as requested (retries={retries})...')
                    retries -= 1
                    time.sleep(0.25)
                else:
                    retries = 0
                    if "RspPending" in str(e):
                        # need to do this to avoid the response showing up
                        # in the next request
                        print(f'{service_id:#x} sent RspPending...')
                        try:
                            r2 = kwp.transport.recv(1)
                            print(f'Delayed Response: {r2}')
                        except Exception as e2:
                            print(f'Delayed Error: {e2}')
                            e = e2
                    if "serviceNotSupported" not in str(e):
                        # response that isn't an outright "nope!"
                        print(f"{service_id:#x}: error {e}")
                        result.append(service_id)
            except kwp2000.InvalidServiceIdError as e:
                print(f"{service_id:#x}: error {e}")
                result.append(service_id)  # I guess this counts as a reply?
                retries = 0
            except kwp2000.TimeoutError:
                retries = 0  # No reply

    print(f'{len(result)} services: {", ".join(hex(s) for s in result)}')
    return result


def enumerate_services_for_ids(bus, ids=KNOWN_TXIDS, debug=False):
    """ Go through a list of diagnostic IDs (by default, the known Kona diagnostic IDs)
    and enumerate the diagnostic services on each.
    """
    result = {}
    for txid, name in ids:
        print(f"**********\nScanning {txid:#x} ({name})... ")
        result[txid] = enumerate_services(bus, txid, debug)
    return result


def scan_tester_present(bus):
    """ Go through all possible Diagnostic IDs and return a list of which ones
    give any response to Tester Present service request (including an error response).
    """
    found = []
    for txid in range(0x700, 0x7f7):
        if txid == 0x7bf:
            continue  # broadcast address
        print(f'txid: {txid:#x}: ', end='')

        tp = kwp2000.Session(bus, txid, txid + 8, default_timeout=0.2)
        kwp = kwp2000.KWP2000Client(tp)
        try:
            # UDS style Tester Present data byte
            kwp._kwp(kwp2000.SERVICE_TYPE.TESTER_PRESENT, data=b'\x00')
            print('OK')
            found.append(txid)
        except Exception as e:
            if "No response to request" in str(e):
                print('No response')
            else:
                print(e)
                found.append(txid)
    return found


def read_data_by_common_identifier(bus, txid, identifier, debug=False):
    """ This doesn't currently work, returns "subFunctionNotsupported-invalidFormat"
    """
    tp = kwp2000.Session(bus, txid, txid + 8)
    kwp = kwp2000.KWP2000Client(tp, debug=debug)

    kwp.diagnostic_session_control(0x90)

    data = struct.pack('>HBB',
                     identifier,
                     1,  # transmission mode: single
                     1)  # number of responses to send

    data = b'\x00\x01'

    resp = kwp._kwp(kwp2000.SERVICE_TYPE.READ_DATA_BY_COMMON_IDENTIFIER,
                    data=data)
    return resp
