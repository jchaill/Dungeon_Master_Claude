# Dungeon Master Claude — Player Manual

AI-powered multiplayer D&D 5e, played entirely in the browser.

---

## Table of Contents

1. [What is This?](#1-what-is-this)
2. [Getting the Server Running](#2-getting-the-server-running)
3. [Joining a Campaign](#3-joining-a-campaign)
4. [Creating Your Character](#4-creating-your-character)
5. [The Game Screen](#5-the-game-screen)
6. [Playing the Game](#6-playing-the-game)
7. [Combat](#7-combat)
8. [DM Guide](#8-dm-guide)
9. [Tips & Troubleshooting](#9-tips--troubleshooting)

---

## 1. What is This?

Dungeon Master Claude is a browser-based D&D 5e table. An AI Dungeon Master (powered by a local Ollama language model) narrates the story, responds to player actions, and drives the world forward. Multiple players connect simultaneously in real time — everyone sees the same narrative as it unfolds.

**What you need to play:**
- A modern web browser (Chrome, Firefox, Safari, Edge)
- The server URL from whoever is hosting the game (e.g. `http://192.168.1.10:8000`)

---

## 2. Getting the Server Running

> This section is for the person hosting the game. Players only need the server URL.

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running (local or remote)

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create your environment file
cp .env.example .env
```

Edit `.env` and set:

| Variable | Description | Example |
|---|---|---|
| `OLLAMA_HOST` | URL of your Ollama server | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model to use as DM | `llama3.1:8b-instruct` |
| `DM_PASSWORD` | Password for DM access | `my-secret-pw` |
| `SECRET_KEY` | Random string for JWT signing | `some-long-random-string` |
| `DB_PATH` | SQLite database path | `data/campaigns.db` |
| `CHROMA_PATH` | ChromaDB path (optional RAG) | `data/chroma_db` |

### Start the Server

```bash
cd /path/to/Dungeon_Master_Claude
source .venv/bin/activate
uvicorn src.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

The server is now reachable at `http://<your-ip>:8000`. Share this URL with your players.

---

## 3. Joining a Campaign

Open the server URL in your browser. You will see the campaign lobby.

### If a campaign already exists

1. Find it in the **Active Campaigns** list on the left.
2. Click **Join** next to the campaign name.
3. A popup appears with a dropdown of existing players in that campaign. Either:
   - Select your name from the list if you've played before, or
   - Choose **➕ New player...** and type a new name.
4. Leave the DM password blank (that's only for the DM).
5. Click **Join** — you'll be taken straight to the game.

### If you need to type the Campaign ID manually

Use the **Join a Campaign** form on the right:

1. Enter your **player name**.
2. Enter the **Campaign ID** (ask the DM — it's shown in the campaign list).
3. Leave the DM password blank.
4. Click **Join Campaign**.

### What happens next

You are redirected to the game screen. If you haven't created a character yet, a **+ Character** button appears in the top-right corner — click it before you start playing. The button disappears once your character is saved.

> **Note:** Your session is stored in your browser. If you close the tab and come back, you'll need to join again. Sessions last 24 hours.

---

## 4. Creating Your Character

Click **+ Character** in the top bar of the game screen. This button is only shown if you don't have a character yet.

### Step 1 — Basic Info

| Field | Options |
|---|---|
| Character Name | Any name you like |
| Race | Human, Elf, Dwarf, Halfling, Gnome, Half-Elf, Half-Orc, Tiefling, Dragonborn |
| Class | Barbarian, Bard, Cleric, Druid, Fighter, Monk, Paladin, Ranger, Rogue, Sorcerer, Warlock, Wizard |
| Background | Acolyte, Criminal, Folk Hero, Noble, Outlander, Sage, Soldier, and more |

### Step 2 — Ability Scores

Choose one of three methods using the buttons at the top of the section:

**Standard Array** (recommended for beginners)
Assign the fixed scores `[15, 14, 13, 12, 10, 8]` across your six abilities using the dropdowns. Each score can only be used once.

**Point Buy**
You have 27 points to spend. Scores start at 8 and go up to 15. Higher scores cost more points (14 costs 7 points, 15 costs 9 points). The current spend is shown as you adjust.

**Roll All / Roll**
Click **Roll All** to roll 4d6-drop-lowest for all six abilities at once, or click **Roll** under each individual ability to roll them one at a time.

### Step 3 — Skill Proficiencies

Check the skills your character is proficient in. Each skill shows the linked ability in parentheses. Proficient skills add +2 to relevant checks.

### Step 4 — Backstory

Write a short description of your character's history. The AI DM reads this and will reference it during the game.

### Step 5 — Actions

Add the class features, attacks, and special abilities your character can use (e.g. *Sneak Attack*, *Second Wind*, *Rage*). Type a name and press **Add** or hit Enter. Click **✕** to remove one.

### Step 6 — Known Spells

This section appears only for spellcasting classes (Bard, Cleric, Druid, Paladin, Ranger, Sorcerer, Warlock, Wizard). Add the spells your character has prepared or knows (e.g. *Fireball*, *Cure Wounds*). Same tag-based interface as Actions.

### Step 7 — Inventory

Add the items your character is carrying. For each item:
- Enter a **name** and optional **quantity** on the first row
- Add an optional **description** on the second row
- Press **Add** or hit Enter

Items appear as a list with name, quantity, and description. Click **✕** to remove an item.

### Step 8 — Preview & Save

Once you've picked a class, a **Preview** box shows your calculated starting stats:

- **Max HP** — based on your class hit die + Constitution modifier
- **Armor Class** — 10 + Dexterity modifier (unarmored)
- **Proficiency Bonus** — +2 at level 1

Click **Save Character**. You'll be returned to the game screen and your character will appear in the Players panel for everyone to see.

---

## 5. The Game Screen

The game screen has three panels:

```
┌─────────────┬──────────────────────────────┬─────────────┐
│   Players   │      Narrative / Chat        │   Combat    │
│             │                              │   Tracker   │
│  You: name  │  [story messages appear      │             │
│  [player    │   here in real time]         │  [turn      │
│   cards]    │                              │   order +   │
│             │  [ type your action here ]   │   HP]       │
│  [Ready Up] │                              │             │
└─────────────┴──────────────────────────────┴─────────────┘
```

### Left Panel — Players

The header shows **You: [your name]** so you always know who you are.

Each player has a card showing:
- A green dot when connected, grey when offline
- Character name, race, class, and level
- Current HP / Max HP (turns red when below half; blue temp HP if any)
- A green checkmark if they've clicked Ready Up

**Your own card** is highlighted with a gold border and shows your full character sheet:
- Armor Class and Proficiency Bonus
- All six ability score modifiers (STR / DEX / CON / INT / WIS / CHA)
- Active conditions (if any)
- Skill proficiencies
- Inventory
- Actions
- Known spells (if a spellcaster)

At the bottom is the **Ready Up** button. Click it when you're prepared to begin — it turns gold and signals to the DM that you're set.

### Center Panel — Narrative

This is where the story lives. Messages are colour-coded:

| Colour | Meaning |
|---|---|
| Gold/amber bubble | Dungeon Master narration |
| Your colour (right-aligned) | Your own actions/messages |
| Grey bubble (left-aligned) | Other players' messages |
| Dim, centred text | System events (joins, round starts, etc.) |

While the AI DM is generating a response, a spinner and **"The Dungeon Master is thinking..."** message appears above the input bar, and the input is disabled until the response arrives.

### Right Panel — Combat Tracker

Shows the initiative order and HP for every combatant when combat is active. The currently active combatant is highlighted in gold. Outside of combat this panel shows "No active combat".

---

## 6. Playing the Game

### Sending an Action

Type what your character does in the input box at the bottom of the center panel and press **Enter** or click **Send**.

> **Note:** The DM always refers to you by your **character name**, not your player name. Make sure you've created a character before playing so the AI can address you correctly.

Be as descriptive as you like — the AI DM responds to narrative descriptions, not game-mechanic commands:

> *"I approach the innkeeper cautiously and ask if anyone has been asking about the old ruins to the north."*

> *"I draw my sword and charge at the nearest goblin, swinging for its head."*

> *"I examine the locked chest for traps before trying to pick it."*

The DM will narrate what happens, ask for rolls when appropriate, and advance the story.

### Waiting for the DM

After any player sends an action, the input bar locks and shows a spinner: **"The Dungeon Master is thinking..."** for everyone in the campaign simultaneously. This is normal — the AI is composing a response. Do not refresh the page. The input unlocks automatically when the DM replies.

### Rolling Dice

Click the **🎲** button next to the input to roll a d20. The result appears briefly below the input box. You can describe the roll in your action text:

> *"I rolled a 17 on Perception to search the room."*

For other dice, just include them in your action text and the DM will factor them in.

### Chat vs. Actions

The same input box handles both in-character actions and out-of-character chat. The DM can distinguish context — just be clear:

> *"[OOC] Can we take a short rest before continuing?"*

---

## 7. Combat

Combat is managed by the DM. When it starts, the Combat Tracker on the right becomes active and shows everyone in initiative order.

### During Combat

1. Watch the Combat Tracker — the active combatant is highlighted in gold.
2. When it's **your turn**, describe your action in the chat and send it.
3. The DM advances to the next turn.
4. HP is updated in real time as damage is dealt or healing applied.

If a combatant has status conditions (Poisoned, Stunned, etc.) they appear as small tags beneath their HP in both the combat tracker and your character card.

### Round Tracking

The top bar shows the current round number during combat (e.g. **⚔️ Combat Round 3**). A system message appears in chat whenever a new round begins.

---

## 8. DM Guide

The DM has access to additional controls visible only when logged in with the DM password.

### Creating a Campaign

On the lobby page, use the **Create Campaign** form:

1. Enter a **Campaign Name**.
2. Enter the **DM Password** (set in `.env` as `DM_PASSWORD`).
3. Click **⚔️ Create Campaign**.

You are taken straight to the game screen. Share the Campaign ID (visible in the lobby list) with your players so they can join.

### Deleting a Campaign

In the **Active Campaigns** list, click the red **✕** button next to a campaign. A confirmation modal will ask for the DM password. This permanently deletes all players, characters, and messages associated with the campaign.

### DM Controls (Top Bar)

| Button | Action |
|---|---|
| **Save** | Saves the current campaign state to the database |
| **Pause** | Saves and signals the game is paused |

### Managing Combat

When no combat is active, the right panel shows **⚔️ Start Combat** (DM only).

1. Click **Start Combat** to open the combat setup.
2. Type an NPC/enemy name and HP, then click **Add**. Repeat for each enemy. Player characters are added automatically.
3. Once all enemies are listed, click **Roll Initiative!** — the server rolls initiative for everyone and displays the turn order.
4. Use **Next Turn →** to advance through the order each time a combatant finishes their action.
5. Click **End Combat** when the fight is over.

### Narration Tips

The AI DM generates narration automatically in response to player actions. To steer the story, send an action yourself (as the DM player) describing world events:

> *"A thunderclap echoes through the valley. The sky turns an unnatural shade of crimson."*

The AI will incorporate this into its next response.

---

## 9. Tips & Troubleshooting

**The page shows "Disconnected"**
Your WebSocket connection dropped. Refresh the page — your session is restored automatically if it's less than 24 hours old.

**"No session token — please join a campaign first"**
You navigated directly to the character builder without joining a campaign. Go back to the lobby, join a campaign, then create your character using the **+ Character** button on the game screen.

**"Invalid or expired token"**
Your session has expired (24 hours) or the server restarted. Return to the lobby and join again.

**The DM never responds / the input stays locked**
The Ollama server may be unreachable or the model is taking too long. The input will automatically unlock after 150 seconds. Check `/api/health` in your browser — it will show whether Ollama is connected. The host will need to verify their Ollama setup.

**I refreshed and lost my place**
Your session persists in the browser's localStorage. As long as you don't clear browser data and the session hasn't expired, joining the same campaign again restores everything.

**Can multiple players be in the same campaign?**
Yes — there's no player cap. Everyone connected to the same campaign shares the same chat, narrative, and combat tracker in real time.

**My name appears multiple times in the join dropdown**
This can happen if you joined the same campaign several times previously. All entries refer to the same player — just pick any one with your name.

**The + Character button has disappeared**
This is intentional — it hides once you have a character to prevent accidental duplicate characters. If you need to edit your character, ask the DM.
