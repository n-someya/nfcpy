import sys
sys.path.append("../src")

import nfc

clf = nfc.ContactlessFrontend("usb")
print(clf)
