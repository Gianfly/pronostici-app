import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


URL_FONTE = "https://www.supatips.com/over-1-5-goals-tips"
ROBOTS_URL = "https://www.supatips.com/robots.txt"

FILE_OUTPUT = Path("partite.json")
FILE_DIAGNOSTICA = Path("pagina.html")

QUOTA_MINIMA = 1.30
QUOTA_MASSIMA = 1.50

USER_AGENT = (
    "PronosticiApp/1.0 "
    "(GitHub Actions; aggiornamento giornaliero personale)"
)


def pulisci_testo(valore):
    return re.sub(
        r"\s+",
        " ",
        str(valore or "")
    ).strip()


def accesso_consentito():
    """
    Controlla robots.txt con un limite di tempo.
    Se robots.txt non è verificabile, lo script si interrompe.
    """
    try:
        risposta = requests.get(
            ROBOTS_URL,
            headers={
                "User-Agent": USER_AGENT
            },
            timeout=15
        )

        risposta.raise_for_status()

        parser = RobotFileParser()
        parser.set_url(ROBOTS_URL)
        parser.parse(
            risposta.text.splitlines()
        )

        consentito = parser.can_fetch(
            USER_AGENT,
            URL_FONTE
        )

        print(
            "Accesso consentito da robots.txt:",
            consentito
        )

        return consentito

    except requests.Timeout:
        print(
            "Tempo scaduto durante la lettura "
            "di robots.txt."
        )
        return False

    except Exception as errore:
        print(
            "Impossibile verificare robots.txt:",
            errore
        )
        return False


def scarica_pagina():
    risposta = requests.get(
        URL_FONTE,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
            "Accept-Language": (
                "it-IT,it;q=0.9,en;q=0.7"
            )
        },
        timeout=30
    )

    risposta.raise_for_status()

    return risposta.text


def converti_quota(valore):
    testo = pulisci_testo(
        valore
    ).replace(",", ".")

    corrispondenze = re.findall(
        r"(?<!\d)(\d{1,2}\.\d{1,2})(?!\d)",
        testo
    )

    for corrispondenza in corrispondenze:
        try:
            quota = round(
                float(corrispondenza),
                2
            )

            if (
                QUOTA_MINIMA
                <= quota
                <= QUOTA_MASSIMA
            ):
                return quota

        except ValueError:
            continue

    return None


def estrai_percentuale(valore):
    risultato = re.search(
        r"(?<!\d)(\d{1,3})\s*%",
        pulisci_testo(valore)
    )

    if not risultato:
        return None

    percentuale = int(
        risultato.group(1)
    )

    if 0 <= percentuale <= 100:
        return percentuale

    return None


def estrai_ora(testo):
    risultato = re.search(
        r"\b([01]?\d|2[0-3]):[0-5]\d\b",
        pulisci_testo(testo)
    )

    if risultato:
        return risultato.group(0)

    return ""


def normalizza_data(testo):
    testo_pulito = pulisci_testo(testo)
    oggi = datetime.now().astimezone()

    if re.search(
        r"\b(today|oggi)\b",
        testo_pulito,
        re.IGNORECASE
    ):
        return oggi.strftime("%Y-%m-%d")

    modelli = [
        (
            r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
            "YMD"
        ),
        (
            r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
            "DMY"
        ),
        (
            r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b",
            "DMY"
        )
    ]

    for modello, ordine in modelli:
        risultato = re.search(
            modello,
            testo_pulito
        )

        if not risultato:
            continue

        try:
            if ordine == "YMD":
                anno = int(risultato.group(1))
                mese = int(risultato.group(2))
                giorno = int(risultato.group(3))
            else:
                giorno = int(risultato.group(1))
                mese = int(risultato.group(2))
                anno = int(risultato.group(3))

            return datetime(
                anno,
                mese,
                giorno
            ).strftime("%Y-%m-%d")

        except ValueError:
            continue

    return oggi.strftime("%Y-%m-%d")


def affidabilita_da_dati(
    confidenza,
    quota
):
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


def trova_indice(
    intestazioni,
    parole
):
    for indice, intestazione in enumerate(
        intestazioni
    ):
        testo = intestazione.lower()

        if any(
            parola in testo
            for parola in parole
        ):
            return indice

    return None


def estrai_da_tabelle(soup):
    risultati = []

    for tabella in soup.find_all("table"):
        righe = tabella.find_all("tr")

        if len(righe) < 2:
            continue

        intestazioni = [
            pulisci_testo(
                cella.get_text(
                    " ",
                    strip=True
                )
            )
            for cella in righe[0].find_all(
                ["th", "td"]
            )
        ]

        indice_partita = trova_indice(
            intestazioni,
            [
                "match",
                "partita",
                "fixture"
            ]
        )

        indice_campionato = trova_indice(
            intestazioni,
            [
                "league",
                "campionato",
                "competition"
            ]
        )

        indice_orario = trova_indice(
            intestazioni,
            [
                "time",
                "ora"
            ]
        )

        indice_quota = trova_indice(
            intestazioni,
            [
                "odds",
                "quota"
            ]
        )

        indice_confidenza = trova_indice(
            intestazioni,
            [
                "conf",
                "confidence",
                "prob"
            ]
        )

        titolo = tabella.find_previous(
            ["h2", "h3", "h4"]
        )

        campionato_predefinito = (
            pulisci_testo(
                titolo.get_text(
                    " ",
                    strip=True
                )
            )
            if titolo
            else "Campionato non indicato"
        )

        for riga in righe[1:]:
            celle = [
                pulisci_testo(
                    cella.get_text(
                        " ",
                        strip=True
                    )
                )
                for cella in riga.find_all(
                    ["th", "td"]
                )
            ]

            if not celle:
                continue

            testo_riga = " | ".join(celle)

            mercato_over15 = re.search(
                r"\b("
                r"ov\s*1[.,]5|"
                r"over\s*1[.,]5|"
                r"over/under\s*\(1[.,]5\)"
                r")\b",
                testo_riga,
                re.IGNORECASE
            )

            if not mercato_over15:
                continue

            quota = None

            if (
                indice_quota is not None
                and indice_quota < len(celle)
            ):
                quota = converti_quota(
                    celle[indice_quota]
                )

            if quota is None:
                quota = converti_quota(
                    testo_riga
                )

            if quota is None:
                continue

            partita = ""

            if (
                indice_partita is not None
                and indice_partita < len(celle)
            ):
                partita = celle[
                    indice_partita
                ]

            if not partita:
                candidati = [
                    valore
                    for valore in celle
                    if (
                        len(valore) >= 5
                        and not re.fullmatch(
                            r"[\d.,:%\s\-–]+",
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

            ora = ""

            if (
                indice_orario is not None
                and indice_orario < len(celle)
            ):
                ora = estrai_ora(
                    celle[indice_orario]
                )

            if not ora:
                ora = estrai_ora(
                    testo_riga
                )

            if not partita or not ora:
                continue

            campionato = (
                celle[indice_campionato]
                if (
                    indice_campionato
                    is not None
                    and indice_campionato
                    < len(celle)
                )
                else campionato_predefinito
            )

            confidenza = None

            if (
                indice_confidenza is not None
                and indice_confidenza
                < len(celle)
            ):
                confidenza = (
                    estrai_percentuale(
                        celle[
                            indice_confidenza
                        ]
                    )
                )

            if confidenza is None:
                confidenza = (
                    estrai_percentuale(
                        testo_riga
                    )
                )

            risultati.append({
                "data": normalizza_data(
                    testo_riga
                ),
                "partita": partita,
                "campionato": campionato,
                "ora": ora,
                "quota": quota,
                "affidabilita": (
                    affidabilita_da_dati(
                        confidenza,
                        quota
                    )
                )
            })

    return risultati


def estrai_da_blocchi(soup):
    risultati = []

    selettori = [
        "article",
        ".match",
        ".fixture",
        ".prediction",
        ".tip",
        ".game",
        ".event",
        ".row",
        "li"
    ]

    elementi = soup.select(
        ",".join(selettori)
    )

    for elemento in elementi:
        testo = pulisci_testo(
            elemento.get_text(
                " ",
                strip=True
            )
        )

        if (
            len(testo) < 15
            or len(testo) > 800
        ):
            continue

        if not re.search(
            r"\b("
            r"ov\s*1[.,]5|"
            r"over\s*1[.,]5"
            r")\b",
            testo,
            re.IGNORECASE
        ):
            continue

        quota = converti_quota(testo)
        ora = estrai_ora(testo)

        if quota is None or not ora:
            continue

        collegamenti = elemento.find_all("a")

        nomi = [
            pulisci_testo(
                collegamento.get_text(
                    " ",
                    strip=True
                )
            )
            for collegamento in collegamenti
            if len(
                pulisci_testo(
                    collegamento.get_text(
                        " ",
                        strip=True
                    )
                )
            ) >= 3
        ]

        partita = ""

        if len(nomi) >= 2:
            partita = (
                nomi[0]
                + " - "
                + nomi[1]
            )

        if not partita:
            partita = testo[:100]

        titolo = elemento.find_previous(
            ["h2", "h3", "h4"]
        )

        campionato = (
            pulisci_testo(
                titolo.get_text(
                    " ",
                    strip=True
                )
            )
            if titolo
            else "Campionato non indicato"
        )

        confidenza = (
            estrai_percentuale(testo)
        )

        risultati.append({
            "data": normalizza_data(testo),
            "partita": partita,
            "campionato": campionato,
            "ora": ora,
            "quota": quota,
            "affidabilita": (
                affidabilita_da_dati(
                    confidenza,
                    quota
                )
            )
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
            or partita["quota"]
            < esistente["quota"]
        ):
            uniche[chiave] = partita

    return list(
        uniche.values()
    )


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


def main():
    print("VERSIONE CORRETTA 2026-09-02")

    if not accesso_consentito():
        print(
            "Accesso automatico non consentito "
            "o robots.txt non verificabile."
        )
        sys.exit(1)

    html = scarica_pagina()

    print(
        "HTML scaricato:",
        len(html),
        "caratteri"
    )

    FILE_DIAGNOSTICA.write_text(
        html,
        encoding="utf-8"
    )

    print(
        "Pagina diagnostica salvata in pagina.html"
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    partite = estrai_da_tabelle(
        soup
    )

    print(
        "Risultati da tabelle:",
        len(partite)
    )

    if not partite:
        partite = estrai_da_blocchi(
            soup
        )

        print(
            "Risultati da blocchi:",
            len(partite)
        )

    partite = rimuovi_duplicati(
        partite
    )

    partite = ordina_partite(
        partite
    )

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
        "Aggiornamento completato:",
        len(partite),
        "partite salvate."
    )


if __name__ == "__main__":
    main()
