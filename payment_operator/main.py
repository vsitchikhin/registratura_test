from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/payments", status_code=202)
async def create_payment():
    return {"status": "accepted"}
