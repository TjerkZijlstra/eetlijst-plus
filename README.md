
Zie in Home Assistant of je ingeschreven staat, schrijf jezelf in of uit, en beheer de boodschappenlijst. Werkt met de developer API van de nieuwe Eetlijst (v5).

Inclusief een eigen dashboardkaart in Eetlijst-stijl: je week in gekleurde rondjes, en met één tik inschrijven.

## Installeren via HACS

1. Ga in Home Assistant naar **HACS → ⋮ → Aangepaste repositories**.
2. Plak `https://github.com/TjerkZijlstra/eetlijst-plus`, kies type **Integratie** en klik op **Toevoegen**.
3. Zoek **Eetlijst+** in HACS, klik op **Downloaden** en herstart Home Assistant.
4. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen → Eetlijst+**.
5. Plak je API key. Die vind je op <https://v5.eetlijst.nl/account> onder **Developer API key**.

Zit je in meerdere Eetlijsten, dan kies je er daarna één. Voor elke lijst kun je de integratie opnieuw toevoegen.

Zonder HACS kan het ook: kopieer de map `custom_components/eetlijst_plus` naar `/config/custom_components/` en herstart Home Assistant.

## Dashboardkaart

De kaart wordt automatisch meegeleverd. Voeg hem toe via **Kaart toevoegen → Handmatig**:

```yaml
type: custom:eetlijst-card
```

Je ziet de komende 7 dagen. Elke status is een gekleurd rondje:

| Rondje | Status |
|---|---|
| Oranje, koksmuts | Koken |
| Groen, vinkje | Mee-eten |
| Lichtblauw, winkelwagen | Boodschappen |
| Rood, kruis | Niet mee-eten |
| Grijs, vraagteken | Weet nog niet |

Tik op je eigen rondje om je status voor die dag te kiezen en het aantal gasten aan te passen. Onderaan en rechtsboven staat het totaal aantal eters, gasten meegeteld. Gesloten dagen krijgen een slotje.

**Opties**

| Optie | Standaard | Wat |
|---|---|---|
| `housemates` | `true` | `false` toont alleen je eigen rij plus de totalen |
| `cook` | `true` | toont onder de titel wie er vandaag kookt; `false` verbergt die regel |
| `days` | `7` | Aantal dagen (1 t/m 7) |
| `title` | naam van je lijst | Eigen titel |

Voorbeeld voor een compacte kaart op je telefoon:

```yaml
type: custom:eetlijst-card
housemates: false
days: 5
```

Krijg je "Custom element doesn't exist: eetlijst-card"? Herstart Home Assistant en ververs je browser met Ctrl+F5. Werkt dat niet, voeg dan bij **Instellingen → Dashboards → ⋮ → Bronnen** de bron `/eetlijst_plus/eetlijst-card.js` toe als **JavaScript-module**.

## Entiteiten

| Entiteit | Wat |
|---|---|
| `select` Mijn status vandaag / morgen | Je huidige status, en direct aan te passen |
| `binary_sensor` Ingeschreven vandaag / morgen | Aan als je koken, mee-eten of boodschappen hebt gekozen |
| `binary_sensor` Inschrijving open | Of de lijst van vandaag nog open staat |
| `number` Mijn gasten vandaag | Aantal gasten dat je meeneemt |
| `sensor` Eters vandaag | Aantal eters inclusief gasten, met als attributen wie kookt, mee-eet, niet eet, enz. |
| `sensor` Kok vandaag | Naam van de kok, of "Niemand" |
| `sensor` per huisgenoot | Status van vandaag, met in de attributen de komende 7 dagen |
| `todo` Boodschappenlijst | Items toevoegen, afvinken en verwijderen |
| `sensor` API key verloopt | Wanneer je key verloopt (diagnostisch) |

De icoontjes van de entiteiten wisselen mee met de status (koksmuts, bestek, winkelwagen enz.).

## Actie: `eetlijst_plus.set_status`

Hiermee schrijf je je in voor een willekeurige dag, wat handig is in automatiseringen:

```yaml
action: eetlijst_plus.set_status
data:
  date: "2026-10-14"     # optioneel, standaard vandaag
  status: eat_only       # eat_only | cook | got_groceries | not_attending | dont_know_yet
  guests: 1              # optioneel
  comment: "Ben om 19:00 thuis"   # optioneel; een lege tekst wist de opmerking
```

Voorbeeld: elke werkdag om 15:00 een melding als je nog niets hebt ingevuld.

```yaml
triggers:
  - trigger: time
    at: "15:00:00"
conditions:
  - condition: time
    weekday: [mon, tue, wed, thu, fri]
  - condition: state
    entity_id: select.eetlijst_jouw_lijst_mijn_status_vandaag   # pas aan naar jouw entity_id
    state: ["dont_know_yet", "unknown"]
actions:
  - action: notify.mobile_app_jouw_telefoon
    data:
      message: "Je hebt je nog niet ingeschreven op de Eetlijst"
```

## Verlopen API key

Als de key verloopt, verschijnt er een melding in Home Assistant om een nieuwe in te vullen. Je kunt hem ook zelf vervangen via de integratie: **⋮ → Opnieuw configureren**.

## Goed om te weten

- Eetlijst wordt elke 2 minuten opgehaald. Na een wijziging ververst hij meteen.
- "Boodschappen" telt mee als eter.
- Is de lijst al gesloten, dan weigert Eetlijst de wijziging. Je ziet dan de foutmelding van Eetlijst in Home Assistant.
- Dit is een onofficiële integratie en wordt niet door Eetlijst ondersteund.
