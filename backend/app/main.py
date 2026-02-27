"""
Main module that runs the whole application.
"""

from fastapi import FastAPI

from utils import logging

logging.setup_logger()
logger = logging.get_logger(__name__)
app = FastAPI()  # TODO: Close redis on application closing


@app.get("/")
async def root():
    """
    Root endpoint.
    :return: HTTP response
    """
    return {"message": "Hello World!"}
