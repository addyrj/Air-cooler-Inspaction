import logging
import json
import sys
from pathlib import Path
from datetime import datetime

LOG_FILE = Path(__file__).parents[4] / "logs" / "inspection.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

class _JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "ts": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = _JsonFormatter()
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.addHandler(fh)
    logger.propagate = False
    return logger
