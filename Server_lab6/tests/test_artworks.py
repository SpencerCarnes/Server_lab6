import pytest

def test_list_artworks_empty(client):
    response = client.get("/artworks/")

    assert response.status_code == 200
    assert response.json() == []

def test_get_seeded_artwork(client, seeded_db):
    # Arrange: seeded_db has already loaded the 11 artworks (the Mona Lisa is first).
    expected = {"id": 1, **seeded_db[0]}

    # Act
    response = client.get("/artworks/1")

    # Assert
    assert response.status_code == 200
    assert response.json() == expected

def test_create_artwork(client, sample_artwork):
    response = client.post("/artworks/", json=sample_artwork)

    assert response.status_code == 201
    response_data = response.json()
    assert isinstance(response_data["id"], int)
    assert {key: value for key, value in response_data.items() if key != "id"} == sample_artwork

def test_create_artwork_is_saved(client, created_artwork):
    artwork_id = created_artwork["id"]

    response = client.get(f"/artworks/{artwork_id}")

    assert response.status_code == 200
    assert response.json() == created_artwork

def test_update_artwork(client, created_artwork, updated_artwork):
    artwork_id = created_artwork["id"]
    expected = {"id": artwork_id, **updated_artwork}

    update_response = client.put(
        f"/artworks/{artwork_id}",
        json=updated_artwork,
    )
    get_response = client.get(f"/artworks/{artwork_id}")

    assert update_response.status_code == 200
    assert update_response.json() == expected
    assert get_response.status_code == 200
    assert get_response.json() == expected

def test_delete_artwork(client, created_artwork):
    artwork_id = created_artwork["id"]

    delete_response = client.delete(f"/artworks/{artwork_id}")
    get_response = client.get(f"/artworks/{artwork_id}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert get_response.status_code == 404
 
@pytest.mark.parametrize(
    "method, use_body",
    [
        ("get", False),
        ("put", True),
        ("delete", False),
    ],
    ids=["get", "put", "delete"],
)
def test_artwork_not_found(client, sample_artwork, method, use_body):
    kwargs = {"json": sample_artwork} if use_body else {}
    response = client.request(method, "/artworks/9999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Artwork not found"}
 
def test_non_integer_id(client):
    response = client.get("/artworks/mona-lisa")
 
    assert response.status_code == 422
 
def test_create_duplicate(client, created_artwork, sample_artwork):
    response = client.post("/artworks/", json=sample_artwork)
 
    assert response.status_code == 409
    assert response.json() == {
        "detail": "An artwork with that title and artist already exists"
    }
 
def test_create_duplicate_ignores_case(client, created_artwork, sample_artwork):
    shouting_duplicate = {
        **sample_artwork,
        "title": sample_artwork["title"].upper(),
        "artist": sample_artwork["artist"].lower(),
    }
    response = client.post("/artworks/", json=shouting_duplicate)
 
    assert response.status_code == 409
    assert response.json() == {
        "detail": "An artwork with that title and artist already exists"
    }
 
def test_update_into_duplicate(client, seeded_db):
    mona_lisa = seeded_db[0]
    lady_with_an_ermine = seeded_db[1]
    clashing_update = {
        **lady_with_an_ermine,
        "title": mona_lisa["title"],
        "artist": mona_lisa["artist"],
    }
 
    update_response = client.put("/artworks/2", json=clashing_update)
    get_response = client.get("/artworks/2")
 
    assert update_response.status_code == 409
    assert update_response.json() == {
        "detail": "An artwork with that title and artist already exists"
    }
    assert get_response.status_code == 200
    assert get_response.json() == {"id": 2, **lady_with_an_ermine}
 
def test_update_same_title_and_artist_is_allowed(client, created_artwork):
    artwork_id = created_artwork["id"]
    payload = {key: value for key, value in created_artwork.items() if key != "id"}
    payload["museum"] = f"{created_artwork['museum']} (Annex)"
 
    response = client.put(f"/artworks/{artwork_id}", json=payload)
 
    assert response.status_code == 200
    assert response.json() == {"id": artwork_id, **payload}

field_names = ["title", "artist", "year", "medium", "museum", "image_url"]
 
@pytest.mark.parametrize("missing_field", field_names, ids=field_names)
def test_create_missing_field(client, sample_artwork, missing_field):
    payload = {k: v for k, v in sample_artwork.items() if k != missing_field}
 
    response = client.post("/artworks/", json=payload)
 
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", missing_field]
 
@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("year", 3000),
        ("year", "nineteen-oh-seven"),
        ("title", ""),
    ],
    ids=["future-year", "year-not-int", "empty-title"],
)
def test_create_invalid_value(client, sample_artwork, field, bad_value):
    payload = {**sample_artwork, field: bad_value}
 
    response = client.post("/artworks/", json=payload)
 
    assert response.status_code == 422
 
@pytest.mark.parametrize(
    "params, expected_count",
    [
        ({}, 10),
        ({"limit": 3}, 3),
        ({"limit": 0}, 0),
        ({"limit": 100}, 11), 
        ({"skip": 5}, 6),  
        ({"skip": 10}, 1),  
        ({"skip": 11}, 0),  
        ({"skip": 500}, 0),  
        ({"skip": 9, "limit": 5}, 2),
    ],
    ids=[
        "default-limit",
        "limit-3",
        "limit-0",
        "limit-over-data-size",
        "skip-5",
        "skip-10",
        "skip-all",
        "skip-past-end",
        "skip-9-limit-5",
    ],
)
def test_pagination_counts(client, seeded_db, params, expected_count):
    response = client.get("/artworks/", params=params)
 
    assert response.status_code == 200
    assert len(response.json()) == expected_count

@pytest.mark.parametrize(
    "params",
    [
        {"skip": -1},
        {"limit": -1},
        {"limit": 101},
    ],
    ids=["negative-skip", "negative-limit", "limit-over-max"],
)
def test_pagination_invalid(client, seeded_db, params):
    response = client.get("/artworks/", params=params)
 
    assert response.status_code == 422
 
@pytest.mark.parametrize(
    "artist_query, expected_artist_text",
    [
        ("Claude Monet", "claude monet"),
        ("monet", "monet"),
        ("da vinci", "da vinci"),
        ("Nobody Real", None),
    ],
    ids=["full-name", "partial-lowercase", "partial-multiword", "no-match"],
)
def test_filter_by_artist(
    client, seeded_db, artist_query, expected_artist_text
):

    if expected_artist_text is None:
        expected_titles = []
    else:
        expected_titles = [
            a["title"]
            for a in seeded_db
            if expected_artist_text in a["artist"].lower()
        ]
        assert expected_titles
 
    response = client.get("/artworks/", params={"artist": artist_query, "limit": 100})
 
    assert response.status_code == 200
    assert [a["title"] for a in response.json()] == expected_titles