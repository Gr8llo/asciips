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
--fps: Frame rate di esecuzione (default: 25).
--max-ships: Numero massimo di navi contemporanee a schermo (default: 3).
--force-weather: Flag opzionale di debug (clear, rain, snow, storm) per simulare meteo senza rete.
## Modulo Meteo Asincrono (weather_thread.py)
API usata: Open-Meteo (endpoint geocoding + endpoint forecast, nessun token richiesto).Frequenza aggiornamento: Polling ogni 10 minuti (600 secondi).Architettura: Thread threading.Thread(daemon=True) con scrittura thread-safe su una struttura dati condivisa (WeatherState).Mappatura Meteo:WMO 0: Sereno/Soleggiato (sole ad arco, mare calmo).WMO 1-3: Nuvoloso (nuvole scorrevoli, vento moderato).WMO 51-67, 80-82: Pioggia (particelle oblique, onde alte).WMO 71-77, 85-86: Neve (particelle lente, banchisa ghiacciata).WMO 95-99: Temporale (fulmini con flash a schermo, mare molto mosso).
## Comportamento Navale e Battaglia (ship.py, projectile.py)
Non-determinismo: Le navi spawnano a intervalli casuali dai margini dello schermo con velocità e sprite diversi.Vele dinamiche: Ogni nave seleziona casualmente una stringa da sail_banners in phrases.json e la centra sulle vele ASCII.Cannoneggiamento verbale: Quando due navi sono a distanza di tiro, viene lanciato a intervalli casuali un proiettile contenente una stringa da cannon_insults.Fisica proiettile: Moto parabolico ($y(t) = y_0 + v_y t - \frac{1}{2} g t^2$).Danni e Affondamento:Ogni colpo riduce i punti scafo della nave bersaglio.A 0 HP, la nave entra nello stato SINKING: sprite danneggiato/fumo, scorrimento verso il basso oltre la linea del mare e rimozione.Timer casuale per il respawn di una nuova nave.
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
