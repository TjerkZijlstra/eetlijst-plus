# Eetlijst+ voor Home Assistant

Zie in Home Assistant of je ingeschreven staat, schrijf jezelf in of uit, en beheer de boodschappenlijst. Werkt met de developer API van de nieuwe Eetlijst (v5).

## Installeren

1. Kopieer de map `custom_components/eetlijst_plus` naar `/config/custom_components/` van je Home Assistant (bijv. met de File editor, Samba of `scp`).
2. Herstart Home Assistant.
3. **Instellingen → Apparaten & diensten → Integratie toevoegen → "Eetlijst+"**.
4. Plak je API key: ga naar <https://v5.eetlijst.nl/account> en klik op **Developer API key**.

Zit je in meerdere Eetlijsten, dan kies je er daarna één. Voor elke lijst kun je de integratie opnieuw toevoegen.

## Wat je krijgt

| Entiteit | Wat |
|---|---|
| `select` Mijn status vandaag / morgen | Je huidige status, en direct aan te passen (Mee-eten, Koken, Boodschappen, Niet mee-eten, Weet nog niet) |
| `binary_sensor` Ingeschreven vandaag / morgen | Aan als je koken, mee-eten of boodschappen hebt gekozen |
| `binary_sensor` Inschrijving open | Of de lijst van vandaag nog open staat |
| `number` Mijn gasten vandaag | Aantal gasten dat je meeneemt |
| `sensor` Eters vandaag | Aantal eters inclusief gasten, met als attributen wie kookt, mee-eet, niet eet, enz. |
| `sensor` Kok vandaag | Naam van de kok, of "Niemand" |
| `sensor` per huisgenoot | Status van vandaag, met in de attributen de komende 7 dagen |
| `todo` Boodschappenlijst | Items toevoegen, afvinken en verwijderen |
| `sensor` API key verloopt | Wanneer je key verloopt (diagnostisch) |

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
    entity_id: select.eetlijst_huize_test_mijn_status_vandaag   # pas aan naar jouw entity_id
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
