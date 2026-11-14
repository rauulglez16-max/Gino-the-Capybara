"""Start Gino:  python run.py"""
import logging

import uvicorn

from gino import config

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    print(f"\n  Gino's home: http://{'localhost' if config.HOST in ('127.0.0.1', '0.0.0.0') else config.HOST}:{config.PORT}\n")
    uvicorn.run("gino.server:app", host=config.HOST, port=config.PORT, log_level="warning")
