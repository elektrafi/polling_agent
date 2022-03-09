#!/usr/bin/env python3
__name__ = "efi_polling_agent"

import logging
import logging.handlers

rootLogger = logging.getLogger(__name__)
wfh = logging.handlers.WatchedFileHandler("efi_polling_agent.log")
sh = logging.StreamHandler()
fileFormatter = logging.Formatter(
    "%(asctime)s  --  [%(name)s] <%(levelname)s>: %(message)s\n\tIn: %(filename)s.%(funcName)s\n\t  @ %(lineno)d"
)
consoleFormatter = logging.Formatter("[%(name)s] <%(levelname)s>: %(message)s")
rootLogger.setLevel(logging.DEBUG)
wfh.setLevel(logging.DEBUG)
wfh.setFormatter(fileFormatter)
sh.setLevel(logging.ERROR)
sh.setFormatter(consoleFormatter)
rootLogger.addHandler(wfh)
rootLogger.addHandler(sh)
rootLogger.info("logging initialized")
