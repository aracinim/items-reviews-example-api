Agente: "Necesito revisar las publicaciones del vendedor 10301".
Agente llama a la API: GET /sellers/10301/publications
API Responde: Una lista de publicaciones, incluyendo la de item_id: "MLB1625519812".
Agente: "Ok, voy a analizar el item MLB1625519812. Necesito el resumen de sus reseñas".
Agente llama a la API: GET /items/MLB1625519812/reviews/summary
API Responde: {"rating_average": 2.0, "review_count": 1}.
Agente (Lógica Interna): "El promedio es 2.0. Según mis reglas, si el promedio es 2.0 o menos, debo pausar la publicación. La acción es pausar".
Agente llama a la API: PATCH /publications/MLB1625519812 con el body {"status": "paused"}.
API Responde: La publicación actualizada, ahora con "status": "paused".
Agente: "Acción completada. La publicación MLB1625519812 ha sido pausada"