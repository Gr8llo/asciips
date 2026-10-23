# Product Requirements Document (PRD): AsciiShips

## 1. Visione del Progetto
Uno screensaver/applicazione TUI animata in Python nello stile di `asciiquarium`, focalizzata su una battaglia navale procedurale e non deterministica in ASCII art.
Caratteristiche cardine:
- Meteo dinamico in tempo reale prelevato da Open-Meteo in background.
- Rendering grafico avanzato con supporto TrueColor (RGB 24-bit) e gradienti.
- Frasi personalizzate caricate da JSON mostrate sulle vele e sparate come proiettili balistici tra le navi.

---

## 2. Requisiti Tecnici e Stack
- **Linguaggio:** Python 3.10+
- **Libreria TUI principale:** `asciimatics`
- **Networking/HTTP:** `urllib.request` (o `requests`) in thread demone asincrono
- **Palette Colori:** TrueColor / 24-bit ANSI (`\x1b[38;2;R;G;Bm`) con funzioni di interpolazione per gradienti cielo/mare
- **Piattaforma:** Linux (supporto ridimensionamento finestra `SIGWINCH`)

---

## 3. Struttura del Repository
```text
asciiships/
├── PRD.md                  # Questo documento di requisiti
├── navi.py                 # Entry point CLI (argparse, avvio asciimatics)
├── config.py               # Parametri globali, palette RGB, costanti fisiche
├── phrases.json            # Database locale di testi per vele e cannonate
├── engine/
│   ├── __init__.py
│   ├── loop.py             # Game loop e gestione coordinate canvas
│   ├── renderer.py         # Calcolo gradienti colore e drawing buffer
│   └── weather_thread.py   # Thread background per chiamata API Open-Meteo
└── entities/
    ├── __init__.py
    ├── weather.py          # Particelle (pioggia, fiocchi di neve, sole, nuvole)
    ├── sea.py              # Funzione sinusoidale per onde e rollio navale
    ├── ship.py             # Automa nave: HP, stati, movimento e rendering vele
    └── projectile.py       # Traiettoria balistica delle stringhe di testo
```

## 4. Requisiti Funzionali Dettagliati
CLI e Parametri di Avvio (navi.py)Lo script deve accettare argomenti con argparse:
--city: Nome della città per il meteo (default: "Bologna").
--fps: Frame rate di esecuzione (default: 5, minimo supportato: 5, massimo: 120).
--max-ships: Numero massimo di navi contemporanee a schermo (default: 3).
--force-weather: Flag opzionale di debug per simulare uno dei 12 stati meteo senza rete.
--force-weather storm resta un alias compatibile per thunderstorm. Il tasto W scorre i 12 stati e poi torna al meteo live.
Refresh: il tasto F2 diminuisce e F3 aumenta il refresh in passi di 5 FPS (limiti 5-120); il menu mostra il controllo. I tasti +/- continuano a regolare il numero di navi.
Tema: automatico secondo giorno/notte della città; il tasto T scorre Auto, Light e Dark (G/N restano alias) e il menu mostra il controllo.
## Modulo Meteo Asincrono (weather_thread.py)
API usata: Open-Meteo (geocoding e forecast, senza token). Il thread daemon aggiorna ogni 10 minuti, includendo ora locale, indicatore giorno/notte, temperatura, temperatura percepita, umidita' e vento.

Stati meteo: `clear`, `partly-cloudy`, `overcast`, `cloudy`, `drizzle`, `rain`, `rain-showers`, `snow`, `snow-grains`, `fog`, `thunderstorm`, `thunderstorm-hail`. Mappatura WMO: 0 sereno; 1-2 parzialmente nuvoloso (nuvoloso di notte); 3 coperto; 45/48 nebbia; 51-57 pioviggine; 61-67 pioggia; 71-76 e 85-86 neve; 77 granuli di neve; 80-82 rovesci; 95/97/98 temporale; 96/99 temporale con grandine.

Con `snow` e `snow-grains` il mare si ghiaccia e le navi appaiono come rompighiaccio.
## Comportamento Navale e Battaglia (ship.py, projectile.py)
Le navi si muovono automaticamente lungo la superficie prospettica del mare, sia all'orizzonte sia sulle onde visibili piu' in basso; restano sopra il pelo dell'acqua e seguono il profilo della propria corsia. Ogni nave viene disegnata con la dimensione ASCII originale e come sprite rigido. Tutte le onde, inclusa la cresta dell'orizzonte, vengono disegnate dietro alle navi per non coprirne vele e scafi. Quando affonda, la nave resta sul posto e scompare sotto la superficie locale, senza scendere fino al fondo dello schermo. Le navi evitano collisioni sulla stessa corsia e mostrano un profilo ASCII a tre quarti durante le virate, tornando alla vista laterale in navigazione. Velocita' navale dimezzata; intervallo tra i colpi raddoppiato.

## HUD e modalita' visiva
Mostra l'orologio con l'ora locale della citta' e condizione, temperatura, temperatura percepita, umidita' e vento, senza titolo ASCII. In Auto il tema passa a Light di giorno e Dark dopo il tramonto secondo il segnale locale Open-Meteo.
## File Dati Iniziale (phrases.json)JSON{
  "sail_banners": [
    "AUDACES IUVAT",
    "BLACK PEARL",
    "BOLOGNA",
    "VENTO IN POPPA",
    "FLYING DUTCHMAN"
  ],
  "cannon_insults": [
    "FUOCO!",
    "A FONDO!",
    "BOOM!",
    "MISERABILE!",
    "PRENDI QUESTA!"
  ]
}
