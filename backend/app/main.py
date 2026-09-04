from fastapi import FastAPI

app = FastAPI(
    title="Smart Market Watchlist API",
    description="Change-detection and attention-ranking layer over a watchlist.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
