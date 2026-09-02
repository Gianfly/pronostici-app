import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


URL_FONTE = "https://www.supatips.com/over-1-5-goals-tips"
FILE_OUTPUT = Path("partite.json")

QUOTA_MINIMA = 1.30
QUOTA_MASSIMA = 1.50

USER_AGENT = (
    "PronosticiApp/1.0 "
    "(GitHub Actions; aggiornamento giornaliero personale)"
)


def accesso_consentito():
    """
    Controlla robots.txt prima di leggere la pagina.
    In caso di errore di connessione non procede.
    """
    robots_url = "https://www.supatips.com/robots.txt"

    try:
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.read()

        return parser.can_fetch(USER_AGENT, URL_FONTE)

    except Exception as errore:
        print("Impossibile verificare robots.txt:", errore)
        return False


def pulisci_testo(valore):
    return re.sub(r"\s+", " ", str(valore or "")).strip()


def converti_quota(valore):
    testo = pulisci_testo(valore).replace(",", ".")

    risultato = re.search(
        r"\b(1\.\d{1,2}|2\.\d{1,2})\b",
        testo
    )

    if not risultato:
        return None

    try:
        return round(float(risultato.group(1)), 2)
    except ValueError:
        return None


def estrai_percentuale(valore):
    risultato = re.search(
        r"\b(\d{1,3})\s*%",
        pulisci_testo(valore)
    )

    if not risultato:
        return None

    percentuale = int(risultato.group(1))

    if 0 <= percentuale <= 100:
        return percentuale

    return None


def affidabilita_da_confidenza(confidenza, quota):
    """
    Prima usa la confidenza pubblicata dalla fonte.
    Se manca, usa il livello derivato dalla quota.
    """
    if confidenza is not None:
        if confidenza >= 90:
            return "ALTA"

        if confidenza >= 80:
            return "BUONA"

        return "DISCRETA"

    if quota <= 1.36:
        return "ALTA"

    if quota <= 1.43:
        return "BUONA"

    return "DISCRETA"


def normalizza_data(testo_data):
    """
    Converte riferimenti come Today e date numeriche
    nel formato AAAA-MM-GG.
    """
    testo = pulisci_testo(testo_data)
    oggi = datetime.now().astimezone()

    if re.search(r"\b(today|oggi)\b", testo, re.IGNORECASE):
        return oggi.strftime("%Y-%m-%d")

    formati = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y"
    ]

    for formato in formati:
        try:
            return datetime.strptime(
                testo,
                formato
            ).strftime("%Y-%m-%d")
        except ValueError:
            pass

    risultato = re.search(
        r"(\d{1,2})\d{1,2}\d{2,4}",
        testo
    )

    if risultato:
        giorno = int(risultato.group(1))
        mese = int(risultato.group(2))
        anno = int(risultato.group(3))

        if anno < 100:
            anno += 2000

        try:
            return datetime(
                anno,
                mese,
                giorno
            ).strftime("%Y-%m-%d")
        except ValueError:
            return oggi.strftime("%Y-%m-%d")

    return oggi.strftime("%Y-%m-%d")


def estrai_ora(testo):
    risultato = re.search(
        r"\b([01]?\d|2[0-3]):[0-5]\d\b",
        pulisci_testo(testo)
    )

    return risultato.group(0) if risultato else ""


def trova_indice(intestazioni, parole):
    for indice, intestazione in enumerate(intestazioni):
        testo = intestazione.lower()

        if any(parola in testo for parola in parole):
            return indice

    return None


def estrai_da_tabelle(soup):
    risultati = []

    for tabella in soup.find_all("table"):
        righe = tabella.find_all("tr")

        if not righe:
            continue

        intestazioni = [
            pulisci_testo(cella.get_text(" ", strip=True))
            for cella in righe[0].find_all(["th", "td"])
        ]

        indice_partita = trova_indice(
            intestazioni,
            ["match", "partita", "fixture"]
        )

        indice_quota = trova_indice(
            intestazioni,
            ["odds", "quota"]
        )

        indice_pick = trova_indice(
            intestazioni,
            ["pick", "tip", "pronostico"]
        )

        indice_confidenza = trova_indice(
            intestazioni,
            ["conf", "confidence", "prob"]
        )

        indice_orario = trova_indice(
            intestazioni,
            ["time", "ora"]
        )

        campionato_corrente = "Campionato non indicato"

        titolo_precedente = tabella.find_previous(
            ["h2", "h3", "h4"]
        )

        if titolo_precedente:
            campionato_corrente = pulisci_testo(
                titolo_precedente.get_text(" ", strip=True)
            )

        for riga in righe[1:]:
            celle = [
                pulisci_testo(cella.get_text(" ", strip=True))
                for cella in riga.find_all(["th", "td"])
            ]

            if not celle:
                continue

            testo_completo = " | ".join(celle)

            if not re.search(
                r"(Ov\s*1[.,]5|Over\s*1[.,]5)",
                testo_completo,
                re.IGNORECASE
            ):
                continue

            partita = ""

            if (
                indice_partita is not None
                and indice_partita < len(celle)
            ):
                partita = celle[indice_partita]

            if not partita:
                candidati = [
                    valore for valore in celle
                    if (
                        len(valore) >= 5
                        and not re.fullmatch(
                            r"[\d.,:%\s-]+",
                            valore
                        )
                        and not re.search(
                            r"over|under|ov1|un1",
                            valore,
                            re.IGNORECASE
                        )
                    )
                ]

                if candidati:
                    partita = max(
                        candidati,
                        key=len
                    )

            quota = None

            if (
                indice_quota is not None
                and indice_quota < len(celle)
            ):
                quota = converti_quota(
                    celle[indice_quota]
                )

            if quota is None:
                for valore in celle:
                    possibile_quota = converti_quota(valore)

                    if (
                        possibile_quota is not None
                        and QUOTA_MINIMA
                        <= possibile_quota
                        <= QUOTA_MASSIMA
                    ):
                        quota = possibile_quota
                        break

            if quota is None:
                continue

            if not (
                QUOTA_MINIMA
                <= quota
                <= QUOTA_MASSIMA
            ):
                continue

            confidenza = None

            if (
                indice_confidenza is not None
                and indice_confidenza < len(celle)
            ):
                confidenza = estrai_percentuale(
                    celle[indice_confidenza]
                )

            if confidenza is None:
                confidenza = estrai_percentuale(
                    testo_completo
                )

            ora = ""

            if (
                indice_orario is not None
                and indice_orario < len(celle)
            ):
                ora = estrai_ora(
                    celle[indice_orario]
                )

            if not ora:
                ora = estrai_ora(testo_completo)

            data = normalizza_data(testo_completo)

            if not partita or not ora:
                continue

            risultati.append({
                "data": data,
                "partita": partita,
                "campionato": campionato_corrente,
                "ora": ora,
                "quota": quota,
                "affidabilita": affidabilita_da_confidenza(
                    confidenza,
                    quota
                ),
                "confidenza": confidenza
            })

    return risultati


def estrai_da_blocchi(soup):
    """
    Metodo alternativo se il sito non utilizza tabelle HTML.
    """
    risultati = []

    selettori = [
        "article",
        ".match",
        ".fixture",
        ".prediction",
        ".tip",
        ".game",
        "li"
    ]

    elementi = soup.select(",".join(selettori))

    for elemento in elementi:
        testo = pulisci_testo(
            elemento.get_text(" ", strip=True)
        )

        if len(testo) < 15 or len(testo) > 600:
            continue

        if not re.search(
            r"(Ov\s*1[.,]5|Over\s*1[.,]5)",
            testo,
            re.IGNORECASE
        ):
            continue

        quota = converti_quota(testo)

        if quota is None:
            continue

        if not (
            QUOTA_MINIMA
            <= quota
            <= QUOTA_MASSIMA
        ):
            continue

        ora = estrai_ora(testo)

        if not ora:
            continue

        confidenza = estrai_percentuale(testo)

        collegamenti = elemento.find_all("a")

        nomi = [
            pulisci_testo(link.get_text(" ", strip=True))
            for link in collegamenti
            if len(pulisci_testo(
                link.get_text(" ", strip=True)
            )) >= 3
        ]

        partita = " - ".join(nomi[:2])

        if not partita:
            partita = testo[:90]

        titolo = elemento.find_previous(
            ["h2", "h3", "h4"]
        )

        campionato = (
            pulisci_testo(
                titolo.get_text(" ", strip=True)
            )
            if titolo
            else "Campionato non indicato"
        )

        risultati.append({
            "data": normalizza_data(testo),
            "partita": partita,
            "campionato": campionato,
            "ora": ora,
            "quota": quota,
            "affidabilita": affidabilita_da_confidenza(
                confidenza,
                quota
            ),
            "confidenza": confidenza
        })

    return risultati


def rimuovi_duplicati(partite):
    uniche = {}

    for partita in partite:
        chiave = (
            partita["data"].lower(),
            partita["partita"].lower(),
            partita["ora"].lower()
        )

        esistente = uniche.get(chiave)

        if (
            esistente is None
            or partita["quota"] < esistente["quota"]
        ):
            uniche[chiave] = partita

    return list(uniche.values())


def ordina_partite(partite):
    return sorted(
        partite,
        key=lambda elemento: (
            elemento["data"],
            elemento["ora"],
            elemento["campionato"],
            elemento["partita"]
        )
    )


def scarica_pagina():
    risposta = requests.get(
        URL_FONTE,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.7"
        },
        timeout=30
    )

    risposta.raise_for_status()

    return risposta.text


def main():
    if not accesso_consentito():
        print(
            "Accesso automatico non consentito "
            "o robots.txt non verificabile."
        )
        sys.exit(1)

    print("VERSIONE TEST 12345")

    html = scarica_pagina()

    print("HTML scaricato:", len(html))

with open(
    "pagina.html",
    "w",
    encoding="utf-8"
) as f:
    f.write(html)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    partite = estrai_da_tabelle(soup)

    if not partite:
        partite = estrai_da_blocchi(soup)

    partite = rimuovi_duplicati(partite)
    partite = ordina_partite(partite)

    if not partite:
        print(
        "Nessuna partita Over 1.5 valida trovata. "
        "Mantengo il file partite.json esistente."
        )
        sys.exit(0)

    FILE_OUTPUT.write_text(
        json.dumps(
            partite,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(
        f"Aggiornamento completato: "
        f"{len(partite)} partite salvate."
    )


if __name__ == "__main__":
    main()
