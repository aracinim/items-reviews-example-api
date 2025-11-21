from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
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

# --- Modelos para el flujo de Agentes LLM ---

class Publication(BaseModel):
    item_id: str
    seller_id: int
    title: str
    price: float
    stock_quantity: int
    status: Literal["active", "paused", "closed"]

class PublicationUpdate(BaseModel):
    status: Optional[Literal["active", "paused", "closed"]] = None

class ReviewSummary(BaseModel):
    rating_average: float
    review_count: int
    reviews: List[Review]

class BulkActionResponse(BaseModel):
    message: str
    updated_count: int

# -----------------------
# Config de comportamiento
# -----------------------
# Si quieres que rating_levels salga vacío {} (como tu ejemplo), deja True.
# Si quieres calcularlos realmente, pon False.
FORCE_EMPTY_RATING_LEVELS = True

DEFAULT_REVIEWS = {} # Se cargará desde data.json

DATA_PATH = Path(__file__).with_name("data.json")
PUBLICATIONS_PATH = Path(__file__).with_name("publications.json")

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
                return data # type: ignore
    return DEFAULT_REVIEWS

def load_publications() -> Dict[str, Dict[str, Any]]:
    """Carga las publicaciones desde publications.json."""
    if PUBLICATIONS_PATH.exists():
        with PUBLICATIONS_PATH.open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_publications(publications_data: Dict[str, Any]):
    """Guarda el diccionario de publicaciones de vuelta en el archivo JSON."""
    with PUBLICATIONS_PATH.open("w", encoding="utf-8") as f:
        json.dump(publications_data, f, indent=2)

# Cache simple en memoria
REVIEWS_BY_ITEM = load_reviews()
PUBLICATIONS_BY_ITEM = load_publications()

@app.on_event("shutdown")
def on_shutdown():
    """Al cerrar la app, guarda el estado actual de las publicaciones."""
    save_publications(PUBLICATIONS_BY_ITEM)

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

# --- Endpoints Atómicos para Agentes LLM ---

@app.get("/sellers/{seller_id}/publications", response_model=List[Publication], summary="Obtener publicaciones de un vendedor")
def get_seller_publications(seller_id: int):
    """
    Herramienta para obtener todas las publicaciones de un `seller_id`.
    Punto de partida para el flujo de decisión del agente.
    """
    seller_pubs = [
        pub for pub in PUBLICATIONS_BY_ITEM.values()
        if pub.get("seller_id") == seller_id
    ]
    return seller_pubs

@app.get("/items/{item_id}/reviews/summary", response_model=ReviewSummary, summary="Obtener datos y objetos de reseñas de un item")
def get_reviews_summary(item_id: str):
    """
    Herramienta de consulta que devuelve datos agregados y la lista completa
    de reseñas. Diseñado para que el agente tome decisiones basadas en
    métricas y/o en el contenido de las reseñas.
    """
    key = item_id.upper()
    reviews = REVIEWS_BY_ITEM.get(key)
    if reviews is None:
        # Si un item no tiene reseñas, no es un error, devolvemos un resumen vacío.
        return ReviewSummary(rating_average=0.0, review_count=0, reviews=[])

    return ReviewSummary(
        rating_average=compute_average(reviews),
        review_count=len(reviews),
        reviews=[Review(**r) for r in reviews]
    )

@app.patch("/publications/{item_id}", response_model=Publication, summary="Actualizar el estado de una publicación")
def update_publication_status(item_id: str, update_data: PublicationUpdate):
    """
    Herramienta de acción para que el agente modifique una publicación.
    Principalmente usado para cambiar el `status` (ej. a 'paused').
    """
    key = item_id.upper()
    publication = PUBLICATIONS_BY_ITEM.get(key)
    if not publication:
        raise HTTPException(status_code=404, detail=f"Publicación '{item_id}' no encontrada.")

    if update_data.status is not None:
        publication["status"] = update_data.status

    # Devolvemos el objeto completo actualizado
    return publication

@app.post("/publications/activate-all", response_model=BulkActionResponse, summary="Activar todas las publicaciones")
def activate_all_publications():
    """
    Herramienta de acción masiva para establecer el estado de todas las
    publicaciones a 'active'. Útil para reinicios o pruebas.
    """
    updated_count = 0
    for pub_id in PUBLICATIONS_BY_ITEM:
        if PUBLICATIONS_BY_ITEM[pub_id].get("status") != "active":
            PUBLICATIONS_BY_ITEM[pub_id]["status"] = "active"
            updated_count += 1

    return BulkActionResponse(
        message="Todas las publicaciones aplicables han sido activadas.",
        updated_count=updated_count
    )
