"""
Main module that runs the whole application.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    """
    Root endpoint.
    :return: HTTP response
    """
    return {"message": "Hello World!"}
