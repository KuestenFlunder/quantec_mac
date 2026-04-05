# QUANTEC PRO -- Scan-Algorithmus und Sende-Protokoll

**Datum**: 2026-04-05
**Quelle**: Dekompilierter C# Code aus `Hardware.dll` (de4dot + ILSpy)
**Original-Quellpfad**: `C:\QUANTEC\QV7\Hardware\`

---

## 1. Hardware-Schnittstelle (BitBangDevice)

### 1.1 Pin-Belegung des FTDI-Chips

```
Pin  Maske   Name    Richtung    Funktion
---  ------  ------  ----------  --------------------------------
D0   0x01    TXD     Ausgang     Transmit Data
D1   0x02    RXD     Eingang     Receive Data ← RAUSCHGENERATOR-SIGNAL
D2   0x04    RTS     Ausgang     Ready To Send (Diode ON/OFF)
D3   0x08    CTS     Eingang     Clear To Send
D4   0x10    DTR     Ausgang     Steuersignal ON
D5   0x20    DSR     Eingang     Data Set Ready
D6   0x40    DCD     Eingang     Data Carrier Detect
D7   0x80    RI      Eingang     Ring Indicator
```

### 1.2 Steuerbytes

```csharp
byte[] on  = { 0x10 };   // DTR=HIGH → Diode einschalten (Pin D4)
byte[] off = { 0x14 };   // DTR=HIGH + RTS=HIGH → Diode ausschalten (0x10 | 0x04)
```

### 1.3 Konfiguration

```
Baudrate:        57.600
Modus:           AsyncBitBang
Pin-Maske ON:    0x34 (52 dez) = D2+D4+D5 als Ausgang → Bits: 00110100
Pin-Maske OFF:   0x37 (55 dez) = D0+D1+D2+D4+D5 als Ausgang → Bits: 00110111
Lese-Timeout:    5.000 ms
```

### 1.4 Signalquelle

Das **Rauschsignal kommt ueber Pin D1 (RXD)**. Im BitBang-Modus wird D1 als Eingang gelesen:

```csharp
bool isBitSet = (bitBuffer[i] & 0x02) != 0;  // Bit 1 = RXD = Rausch-Pin
```

Die Hardware ist also: **Eine Rauschquelle (Zener-/Schottky-Diode + Verstaerker) die an RXD (Pin D1) des FTDI-Chips angeschlossen ist.**

---

## 2. Grundlegende Lese-Operation

### 2.1 BeginRead -- Diode starten

```
1. FT_SetBitMode(handle, 0x34, AsyncBitBang)   → Pins konfigurieren
2. FT_Write(handle, {0x10}, 1)                  → DTR HIGH = Diode EIN
3. FT_Purge(handle, ReceiveBuffer)              → Empfangspuffer leeren
4. Signalqualitaets-Pruefung:
   - Lese 42 × 32.768 Bytes vom Rauschgenerator
   - Zaehle Nullen und Einsen auf Bit 1 (RXD)
   - Berechne Qualitaet: 1.0 - |zeros - ones| / (zeros + ones)
   - Abbruch wenn Qualitaet < 0.2% (Signal-Dropout)
   - Erfolg wenn Qualitaet > 80% (oder > 40% nach 14+ Runden)
```

### 2.2 EndRead -- Diode stoppen

```
1. FT_SetBitMode(handle, 0x37, AsyncBitBang)   → Alle Pins als Ausgang
2. FT_Write(handle, {0x14}, 1)                  → DTR+RTS = Diode AUS
```

### 2.3 ReadBits -- Rauschbits lesen

```
Fuer jeden angeforderten Bit:
1. Lese (count * average) Raw-Bytes vom FTDI-Chip
2. Pro Byte: Pruefe Bit 1 (RXD): 1 oder 0?
3. Zaehle Nullen/Einsen fuer Signalqualitaet
4. Mittelwert-Bildung: Pro "average" Raw-Bytes → 1 Output-Bit
   - Wenn mehr als die Haelfte der Samples = 1 → Output = 1
   - Sonst → Output = 0
5. Default average = 11 (11 Samples pro Output-Bit)

Signal-Dropout-Recovery:
- Wenn Qualitaet zu schlecht: Diode AUS → Diode EIN → 14 Runden verwerfen → weiter
```

### 2.4 ReadBytes -- Zufalls-Bytes lesen

```
Pro Byte: 8 × ReadBits aufrufen, Bits zu einem Byte zusammensetzen
```

---

## 3. Scan-Algorithmus (5 Varianten)

Alle Scan-Methoden haben dieselbe Signatur:

```csharp
bool Scan(DiodeOperation operation, int[] data, int cycles, ref bool cancel)
```

**Parameter:**
- `data[]` = Array mit einem Slot pro Morphischem-Feld-Eintrag (z.B. 21 Slots)
- `cycles` = Anzahl Scan-Durchlaeufe (Standard: 88)
- Ergebnis: Jeder Slot wird incrementiert wenn er "getroffen" wird. Hoechster Wert = relevantester Eintrag.

### 3.1 SelectionDiode (Standard-Scan)

**Der Haupt-Scan-Algorithmus:**

```
Eingabe: data[N] (N = Anzahl Morphische Felder), cycles
Gesamt-Iterationen: N × cycles

1. Berechne: average = 1 + log2(N)
   (z.B. N=21 → average = 5, N=256 → average = 9)

2. Fuer jede Iteration:
   a. Lese 1 Bit vom Rauschgenerator (mit Mittelwertbildung ueber "average" Samples)
   b. Gehe sequenziell durch die Slots: Position 0, 1, 2, ..., N-1, 0, 1, ...
   c. Wenn das Bit = 1 → data[aktuelle_position]++
   d. Zaehle separat: num4 (Anzahl Einsen), num3 (Anzahl Nullen)

3. Normalisierung am Ende:
   data[j] = data[j] / (num4 / (num3 + num4))
   → Korrigiert fuer die tatsaechliche 0/1-Verteilung des Rauschgenerators
```

**Zusammenfassung**: Jeder Slot bekommt die gleiche Anzahl Chancen "getroffen" zu werden. Die Auswahl basiert auf dem Rauschbit. Am Ende wird auf die tatsaechliche Bias des Generators normalisiert. Die Slots mit den hoechsten Werten sind die "ausgewaehlten" morphischen Felder.

### 3.2 QUANTEC6Diode (Bit-Extraktion)

```
1. Berechne: bits_pro_auswahl = ceil(log2(N))  (z.B. N=21 → 5 Bits)
   bytes_pro_auswahl = ceil(bits_pro_auswahl / 8)

2. Fuer jede Iteration (N × cycles):
   a. Lese "bits_pro_auswahl" Bits vom Rauschgenerator (bitweise aus Byte-Stream)
   b. Bilde daraus eine Zahl (0 bis 2^bits - 1)
   c. Addiere den Wert der vorherigen Iteration (kumulative Verschiebung)
   d. Addiere 1
   e. Modulo N → Index in data[]
   f. data[index]++

Besonderheit: Der Index wird NICHT direkt aus den Zufallsbits genommen,
sondern kumulativ verschoben. Das erzeugt eine Art "Random Walk" durch die Slots.
```

### 3.3 QUANTEC6DiodeWithRandom (Hardware + Software Zufall)

**Identisch zu QUANTEC6Diode, ABER:**

```
- Zusaetzlich: System.Random() Pseudozufallsgenerator
- Nach Bit-Extraktion: index = (hardware_bits + random.Next()) % N
- Kombiniert Hardware-Rauschen mit Software-PRNG
- KEIN kumulativer Walk (kein num4 Carry-Over)
```

### 3.4 DistributionDiode (Verteilungs-Scan)

```
1. Lese (N × 4 × cycles) Bytes vom Rauschgenerator

2. Fuer je 4 Bytes:
   a. Lese uint32 und addiere kumulativ: sum += ReadUInt32()
   b. Berechne: index = (sum * N) >> 32  (obere 32 Bit des 64-Bit Produkts)
   c. data[index]++

Mathematik: (sum * N) >> 32 erzeugt eine Gleichverteilung ueber 0..N-1
aus dem kumulativen Zufallswert. Das ist eine effiziente Modulo-Alternative.
```

### 3.5 RemainderDiode (Rest-basiert)

```
1. Fuer (N × cycles) Iterationen:
   a. Lese 2 × uint32 (8 Bytes) → XOR zu uint64
   b. Iteriere: Fuer jede Potenz von N die in uint64 passt:
      - index = (sum / N^k) % N
      - data[index]++
   c. Nutzt alle Bits des Zufallswerts aus (mehrere Samples pro uint64)
```

---

## 4. Sende-Protokoll

### 4.1 BasicDiode.Send()

```csharp
public override bool Send(TimeSpan duration, ref bool cancel)
{
    // 1. Diode oeffnen und starten
    Device device = Device;
    Begin(DiodeOperation.Send, DiodeState.Sending);
    
    // 2. Initial 1 Byte lesen (Verbindungstest)
    device.ReadBytes(buffer, 0, 1);
    
    // 3. Fuer die gesamte Sendedauer:
    DateTime end = DateTime.Now + duration;
    while (DateTime.Now < end)
    {
        if (cancel) return false;
        
        // LESE Rauschbytes von der Diode (buffer.Length / 4 Bytes)
        device.ReadBytes(buffer, 0, buffer.Length / 4);
    }
    
    // 4. Diode stoppen
    End(DiodeOperation.Send, DiodeState.Idle, success: true);
}
```

### 4.2 Was bedeutet das?

**Beim Senden werden KEINE Daten AN die Diode geschrieben.**

Der Send-Vorgang liest **kontinuierlich Rauschbytes** von der Diode fuer die Dauer der Sendung (Standard: 12 Sekunden). Es werden 1024 Bytes pro Iteration gelesen (`buffer.Length / 4` = 4096/4).

Das bedeutet:
- Die Diode **empfaengt** nichts (kein `FT_Write` im Send-Pfad)
- Die Diode **erzeugt** waehrend der gesamten Sendedauer Rauschbits
- Die Software **liest** diese Bits (und verwirft sie) 
- Gleichzeitig wird auf dem Bildschirm das HealingSheet als Animation dargestellt

**Die "Sendung" ist das gleichzeitige Vorhandensein von:**
1. Visueller Darstellung (HealingSheet auf dem Bildschirm)
2. Aktiver Rauschgenerator (Diode laeuft, Bits werden gelesen)
3. Zeitlich begrenzt (12 Sekunden Standard)

---

## 5. Signalqualitaets-Pruefung

```csharp
bool CheckSignalQuality()
{
    // Wird nach jeweils 32.768 Bits geprueft
    double quality = 1.0 - |zeros - ones| / (zeros + ones);
    
    // Exponentieller Mittelwert:
    signalQuality = 0.9 * signalQuality + 0.1 * quality;
    
    // Dropout wenn quality < 0.2%
    if (quality < 0.002) → FEHLER
    
    // Signal ist gut wenn 0/1 Verteilung nahe 50:50
}
```

Die ideale Signalqualitaet ist **1.0** (exakt 50% Nullen, 50% Einsen). Werte unter 0.2% bedeuten dass der Rauschgenerator nicht funktioniert (z.B. Kabel defekt, Diode nicht angeschlossen).

---

## 6. Zusammenfassung fuer die Mac-Portierung

### Was man braucht:

**Hardware:**
- FTDI FT232R Breakout-Board (z.B. Sparkfun FTDI Basic, ~15 EUR)
- Rauschquelle an Pin D1 (RXD): Zener-Diode + Verstaerker-Schaltung
- Pin D4 (DTR) als Steuerleitung zum Einschalten der Rauschquelle

**Software (Python-Pseudocode):**

```python
import ftd2xx  # oder pyftdi

# Verbinden
dev = ftd2xx.open(0)
dev.setBaudRate(57600)
dev.setBitMode(0x34, 0x20)  # AsyncBitBang, Pins 2+4+5 als Ausgang

# Diode EIN
dev.write(bytes([0x10]))     # DTR HIGH
dev.purge(ftd2xx.PURGE_RX)

# Rauschbits lesen
raw = dev.read(32768)
bits = [(b & 0x02) >> 1 for b in raw]  # Bit 1 (RXD) extrahieren

# Scan: SelectionDiode Algorithmus
def scan(n_fields, cycles):
    data = [0] * n_fields
    average = 1 + int(math.log2(n_fields))
    total = n_fields * cycles
    pos = 0
    ones = zeros = 0
    for _ in range(total):
        bit = read_one_bit(average)  # mit Mittelwertbildung
        if bit:
            data[pos] += 1
            ones += 1
        else:
            zeros += 1
        pos = (pos + 1) % n_fields
    # Normalisieren
    ratio = ones / (ones + zeros)
    return [int(d / ratio) for d in data]

# Senden: Einfach Rauschbits lesen fuer die Dauer
def send(duration_seconds):
    dev.write(bytes([0x10]))  # Diode EIN
    end = time.time() + duration_seconds
    while time.time() < end:
        dev.read(1024)  # Rauschbits lesen (und verwerfen)
    dev.write(bytes([0x14]))  # Diode AUS

# Diode AUS
dev.setBitMode(0x37, 0x20)
dev.write(bytes([0x14]))     # DTR+RTS
dev.close()
```

### Keine Lizenz noetig:

Die Lizenzpruefung (`FTID_GetChipIDFromHandle`) liest nur die Chip-ID und vergleicht sie mit der Lizenzdatei. In unserer eigenen Software ueberspringen wir das einfach. **Jedes FTDI FT232R-Board funktioniert.**

### Rauschquelle bauen:

Minimalschaltung fuer einen Rauschgenerator an RXD (Pin D1):

```
+5V ──┬── 10kΩ ──┬── an D1 (RXD)
      │          │
      │     Zener-Diode (5.1V, rueckwaerts)
      │          │
      └──────────┘
                 │
                GND
```

Die Zener-Diode im Durchbruchbereich erzeugt Rauschen. Der Komparator-Schwellwert des FTDI-Pins (ca. 1.4V) digitalisiert das Rauschen zu 0/1 Bits. Die Signalqualitaetspruefung der Software stellt sicher dass die Verteilung nahe 50:50 liegt.
