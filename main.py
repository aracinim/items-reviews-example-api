from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
import json

app = FastAPI(title="ML-like Reviews API", version="1.0.1")

# -----------------------
# Modelos (shape ML)
# -----------------------
class Review(BaseModel):
    id: int
    reviewable_object: Dict[str, Any] = Field(default_factory=dict)
    date_created: str  # ISO 8601 (e.g., "2019-06-08T14:12:29Z")
    status: str = "published"
    title: str
    content: str
    rate: int = Field(ge=1, le=5)
    valorization: int = 0
    likes: int = 0
    dislikes: int = 0
    reviewer_id: int = 0
    buying_date: Optional[str] = None
    relevance: Optional[int] = None
    forbidden_words: int = 0
    attributes: List[Any] = Field(default_factory=list)

class ReviewsResponse(BaseModel):
    paging: Dict[str, Any] = Field(default_factory=dict)
    # imitamos que ML a veces incluye objetos vacíos en la lista
    reviews: List[Dict[str, Any]]
    rating_average: float
    # Usamos Dict para permitir "{}" vacío si queremos copiar el shape exacto
    rating_levels: Dict[str, int] = Field(default_factory=dict)
    helpful_reviews: List[Any] = Field(default_factory=list)
    attributes: List[Any] = Field(default_factory=list)

# -----------------------
# Config de comportamiento
# -----------------------
# Si quieres que rating_levels salga vacío {} (como tu ejemplo), deja True.
# Si quieres calcularlos realmente, pon False.
FORCE_EMPTY_RATING_LEVELS = True

# -----------------------
# Datos por defecto (usa MLB...).
# Estructura: { item_id: [reviews...] }
# -----------------------
DEFAULT_REVIEWS: Dict[str, List[Dict[str, Any]]] = {
    "MLB1625519814": [
        {
            "id": 43083650,
            "date_created": "2019-06-08T14:12:29Z",
            "status": "published",
            "title": "Iincreíble, lo amo",
            "content": "Impresionante, muy satisfecha con el samsung s9...",
            "rate": 5,
            "valorization": 0,
            "likes": 0,
            "dislikes": 0,
            "reviewer_id": 0,
            "buying_date": "2019-04-12T04:00:00Z",
            "relevance": 71,
            "forbidden_words": 0,
            "attributes": []
        },
        {
            "id": 43083651,
            "date_created": "2019-06-10T09:05:00Z",
            "status": "published",
            "title": "Muy satisfecho",
            "content": "La batería dura bien y la cámara es genial.",
            "rate": 5,
            "valorization": 1,
            "likes": 1,
            "dislikes": 0,
            "reviewer_id": 10300,
            "buying_date": "2019-05-20T04:00:00Z",
            "relevance": 10,
            "forbidden_words": 0,
            "attributes": []
        },
        {
            "id": 43083652,
            "date_created": "2019-06-12T20:00:00Z",
            "status": "published",
            "title": "Podría mejorar",
            "content": "Después de una actualización, falló la alarma.",
            "rate": 3,
            "valorization": 0,
            "likes": 0,
            "dislikes": 1,
            "reviewer_id": 10301,
            "buying_date": "2019-05-10T04:00:00Z",
            "relevance": 5,
            "forbidden_words": 0,
            "attributes": []
        }
    ],
    "MLB1625519801": [
        {
            "id": 43083524,
            "date_created": "2019-07-17T23:11:29Z",
            "status": "published",
            "title": "Perfecto¡¡¡",
            "content": "Excelente producto, recomendable 100%.",
            "rate": 5,
            "valorization": 2,
            "likes": 2,
            "dislikes": 0,
            "reviewer_id": 0,
            "buying_date": "2019-06-22T04:00:00Z",
            "relevance": 4,
            "forbidden_words": 0,
            "attributes": []
        }
    ]
}

DATA_PATH = Path(__file__).with_name("data.json")

def load_reviews() -> Dict[str, List[Dict[str, Any]]]:
    """
    Si existe data.json, se carga y se espera un diccionario:
    {
      "MLB1625519814": [ {review...}, {review...} ],
      "MLB1625519801": [ ... ]
    }
    """
    if DATA_PATH.exists():
        with DATA_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return DEFAULT_REVIEWS

# Cache simple en memoria
REVIEWS_BY_ITEM = load_reviews()

def build_rating_levels(reviews: List[Dict[str, Any]]) -> Dict[str, int]:
    levels = {"one_star": 0, "two_star": 0, "three_star": 0, "four_star": 0, "five_star": 0}
    for r in reviews:
        rate = int(r.get("rate", 0))
        if rate == 1:
            levels["one_star"] += 1
        elif rate == 2:
            levels["two_star"] += 1
        elif rate == 3:
            levels["three_star"] += 1
        elif rate == 4:
            levels["four_star"] += 1
        elif rate == 5:
            levels["five_star"] += 1
    return levels

def compute_average(reviews: List[Dict[str, Any]]) -> float:
    if not reviews:
        return 0.0
    rated = [int(r["rate"]) for r in reviews if r.get("rate") is not None]
    return round(sum(rated) / len(rated), 2) if rated else 0.0

def pad_with_empty_objects(reviews: List[Dict[str, Any]], pre: int = 3, post: int = 1) -> List[Dict[str, Any]]:
    """
    Replica el patrón de tu ejemplo:
    tres {} al inicio y uno {} al final.
    """
    if not reviews:
        return reviews
    return ([{}] * pre) + reviews + ([{}] * post)

# ---------------------------------
# Endpoint: GET /reviews/item/{id}
# ---------------------------------
@app.get("/reviews/item/{item_id}", response_model=ReviewsResponse, summary="Obtener reviews por Item ID (formato ML)")
def get_reviews(
    item_id: str,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    key = item_id.upper()
    reviews_raw = REVIEWS_BY_ITEM.get(key)
    if reviews_raw is None:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    # Convertimos cada review a modelo y luego a dict (para mantener shape y defaults)
    reviews_models = [Review(**r) for r in reviews_raw]
    reviews_dicts = [r.model_dump() for r in reviews_models]

    rating_average = compute_average(reviews_dicts)
    rating_levels = {} if FORCE_EMPTY_RATING_LEVELS else build_rating_levels(reviews_dicts)

    reviews_out = pad_with_empty_objects(reviews_dicts, pre=3, post=1)

    return ReviewsResponse(
        paging={},
        reviews=reviews_out,
        rating_average=rating_average,
        rating_levels=rating_levels,
        helpful_reviews=[],   # lista vacía como tu ejemplo
        attributes=[],        # lista vacía como tu ejemplo
    )
