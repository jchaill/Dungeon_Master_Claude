"""
Character creation tests — covers API, rules engine, dice roller, and campaign sync.
"""
import asyncio
import pytest
import pytest_asyncio
import httpx
import tempfile
import os
from httpx import ASGITransport

# ─── Setup ────────────────────────────────────────────────────────────────────

# Point to a temp file DB — aiosqlite :memory: opens a fresh DB per connection
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

os.environ["DB_PATH"] = _tmp_db.name
os.environ["CHROMA_PATH"] = "/tmp/test_chroma"
os.environ["DM_PASSWORD"] = "testpass"
os.environ["SECRET_KEY"] = "test-secret-key"

from src.main import socket_app
from src import config
config.settings.DB_PATH = _tmp_db.name
config.settings.DM_PASSWORD = "testpass"
config.settings.SECRET_KEY = "test-secret-key"

from src.managers.state_manager import init_db


@pytest_asyncio.fixture
async def client():
    # Fresh DB file per test
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    config.settings.DB_PATH = tmp.name
    await init_db()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=socket_app), base_url="http://test"
    ) as c:
        yield c
    os.unlink(tmp.name)


async def create_campaign_and_join(client, dm=False):
    """Helper: create a campaign and return (campaign_id, token)."""
    res = await client.post("/api/sessions", json={
        "name": "Test Campaign",
        "dm_password": "testpass",
    })
    assert res.status_code == 200, res.text
    data = res.json()
    campaign_id = data["campaign"]["id"]
    token = data["token"]

    if not dm:
        # Join as a regular player
        res2 = await client.post("/api/auth/join", json={
            "player_name": "Alice",
            "campaign_id": campaign_id,
        })
        assert res2.status_code == 200, res2.text
        token = res2.json()["token"]

    return campaign_id, token


CHARACTER_PAYLOAD = {
    "name": "Theron",
    "race": "Elf",
    "class_name": "Ranger",
    "background": "Outlander",
    "abilities": {
        "strength": 12,
        "dexterity": 16,
        "constitution": 14,
        "intelligence": 10,
        "wisdom": 14,
        "charisma": 8,
    },
    "skills": {"perception": True, "stealth": True},
    "backstory": "A wanderer from the northern forests.",
}


# ─── Dice roller tests ────────────────────────────────────────────────────────

def test_dice_roll_notation():
    from src.services.dice_roller import roll
    r = roll("2d6+3")
    assert len(r.rolls) == 2
    assert all(1 <= x <= 6 for x in r.rolls)
    assert r.modifier == 3
    assert r.total == sum(r.rolls) + 3

def test_dice_roll_d20():
    from src.services.dice_roller import roll
    r = roll("d20")
    assert len(r.rolls) == 1
    assert 1 <= r.total <= 20

def test_dice_roll_ability_score():
    from src.services.dice_roller import roll_ability_score
    for _ in range(20):
        r = roll_ability_score()
        assert 3 <= r.total <= 18
        assert len(r.rolls) == 4  # rolled 4, kept 3

def test_dice_invalid_notation():
    from src.services.dice_roller import roll
    with pytest.raises(ValueError):
        roll("not-dice")

def test_dice_invalid_sides():
    from src.services.dice_roller import roll
    with pytest.raises(ValueError):
        roll("1d7")


# ─── Rules engine tests ───────────────────────────────────────────────────────

def test_ability_modifier():
    from src.services.rules_engine import ability_modifier
    assert ability_modifier(10) == 0
    assert ability_modifier(12) == 1
    assert ability_modifier(8)  == -1
    assert ability_modifier(20) == 5
    assert ability_modifier(1)  == -5

def test_proficiency_bonus():
    from src.services.rules_engine import proficiency_bonus
    assert proficiency_bonus(1)  == 2
    assert proficiency_bonus(4)  == 2
    assert proficiency_bonus(5)  == 3
    assert proficiency_bonus(9)  == 4
    assert proficiency_bonus(17) == 6
    assert proficiency_bonus(20) == 6

def test_calculate_hp():
    from src.services.rules_engine import calculate_hp
    # Fighter (d10) level 1, CON 14 (+2) → 10 + 2 = 12
    assert calculate_hp("Fighter", 1, 2) == 12
    # Wizard (d6) level 1, CON 10 (+0) → 6
    assert calculate_hp("Wizard", 1, 0) == 6
    # HP never below level
    assert calculate_hp("Wizard", 1, -5) >= 1

def test_calculate_ac():
    from src.services.rules_engine import calculate_ac
    # No armor, DEX +2 → 12
    assert calculate_ac(2, "none") == 12
    # Leather + DEX +3 → 14
    assert calculate_ac(3, "leather") == 14
    # Chain mail (heavy) → 16, no DEX
    assert calculate_ac(5, "chain mail") == 16


# ─── API: dice endpoints ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_dice_roll(client):
    res = await client.post("/api/dice/roll", json={"notation": "2d6+3"})
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "rolls" in data
    assert len(data["rolls"]) == 2

@pytest.mark.asyncio
async def test_api_dice_ability(client):
    res = await client.post("/api/dice/ability")
    assert res.status_code == 200
    data = res.json()
    assert 3 <= data["total"] <= 18

@pytest.mark.asyncio
async def test_api_standard_array(client):
    res = await client.get("/api/dice/standard-array")
    assert res.status_code == 200
    assert res.json()["scores"] == [15, 14, 13, 12, 10, 8]


# ─── API: character CRUD ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_character(client):
    campaign_id, token = await create_campaign_and_join(client)
    res = await client.post(
        "/api/characters",
        json=CHARACTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"] == "Theron"
    assert data["race"] == "Elf"
    assert data["class_name"] == "Ranger"
    assert data["max_hp"] > 0
    assert data["armor_class"] >= 10
    assert data["proficiency_bonus"] == 2
    assert "id" in data

@pytest.mark.asyncio
async def test_character_hp_calculated_correctly(client):
    campaign_id, token = await create_campaign_and_join(client)
    res = await client.post(
        "/api/characters",
        json=CHARACTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    data = res.json()
    # Ranger (d10), CON 14 (+2) → max_hp = 10 + 2 = 12
    assert data["max_hp"] == 12
    assert data["current_hp"] == data["max_hp"]

@pytest.mark.asyncio
async def test_character_ac_calculated_correctly(client):
    campaign_id, token = await create_campaign_and_join(client)
    res = await client.post(
        "/api/characters",
        json=CHARACTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    data = res.json()
    # DEX 16 (+3), no armor → AC = 13
    assert data["armor_class"] == 13

@pytest.mark.asyncio
async def test_character_synced_to_campaign(client):
    campaign_id, token = await create_campaign_and_join(client)
    res = await client.post(
        "/api/characters",
        json=CHARACTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    char_id = res.json()["id"]

    # Verify character appears in campaign state
    res2 = await client.get(f"/api/sessions/{campaign_id}")
    assert res2.status_code == 200
    campaign_chars = res2.json()["campaign"]["player_characters"]
    assert any(c["id"] == char_id for c in campaign_chars), \
        f"Character {char_id} not found in campaign player_characters"

@pytest.mark.asyncio
async def test_multiple_characters_all_persist(client):
    campaign_id, token = await create_campaign_and_join(client)
    ids = []
    for i in range(3):
        payload = {**CHARACTER_PAYLOAD, "name": f"Hero{i}"}
        res = await client.post(
            "/api/characters",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        ids.append(res.json()["id"])

    res = await client.get(f"/api/sessions/{campaign_id}")
    campaign_chars = res.json()["campaign"]["player_characters"]
    campaign_char_ids = [c["id"] for c in campaign_chars]
    for cid in ids:
        assert cid in campaign_char_ids, f"Character {cid} missing from campaign"

@pytest.mark.asyncio
async def test_get_character(client):
    campaign_id, token = await create_campaign_and_join(client)
    create_res = await client.post(
        "/api/characters",
        json=CHARACTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    char_id = create_res.json()["id"]

    res = await client.get(
        f"/api/characters/{char_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["id"] == char_id

@pytest.mark.asyncio
async def test_update_character(client):
    campaign_id, token = await create_campaign_and_join(client)
    create_res = await client.post(
        "/api/characters",
        json=CHARACTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    char_id = create_res.json()["id"]

    res = await client.put(
        f"/api/characters/{char_id}",
        json={"current_hp": 5, "conditions": ["poisoned"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["current_hp"] == 5
    assert "poisoned" in data["conditions"]

@pytest.mark.asyncio
async def test_cannot_edit_other_players_character(client):
    campaign_id, token1 = await create_campaign_and_join(client)

    # Second player joins
    res = await client.post("/api/auth/join", json={
        "player_name": "Bob",
        "campaign_id": campaign_id,
    })
    token2 = res.json()["token"]

    # Player 1 creates character
    char_res = await client.post(
        "/api/characters",
        json=CHARACTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token1}"},
    )
    char_id = char_res.json()["id"]

    # Player 2 tries to edit it
    res = await client.put(
        f"/api/characters/{char_id}",
        json={"current_hp": 1},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_delete_character(client):
    campaign_id, token = await create_campaign_and_join(client)
    char_res = await client.post(
        "/api/characters",
        json=CHARACTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    char_id = char_res.json()["id"]

    res = await client.delete(
        f"/api/characters/{char_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    res2 = await client.get(
        f"/api/characters/{char_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 404

@pytest.mark.asyncio
async def test_unauthenticated_character_creation(client):
    res = await client.post("/api/characters", json=CHARACTER_PAYLOAD)
    assert res.status_code == 401
