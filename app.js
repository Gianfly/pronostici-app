const API_KEY = "fbfc72a65736699d483a2c09ec4621c5";

async function caricaDati() {

  document.getElementById("over").innerHTML = "Caricamento...";
  document.getElementById("under").innerHTML = "Caricamento...";

  try {

    const response = await fetch(
      "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?" +
      "apiKey=" + API_KEY +
      "&regions=eu" +
      "&markets=totals" +
      "&oddsFormat=decimal"
    );

    const data = await response.json();

    let overHTML = "";
    let underHTML = "";

    data.forEach(match => {

      const partita =
        match.home_team + " - " + match.away_team;

      if (!match.bookmakers?.length) return;

      const bookmaker = match.bookmakers[0];

      if (!bookmaker.markets?.length) return;

      bookmaker.markets.forEach(market => {

        if (market.key !== "totals") return;

        market.outcomes.forEach(outcome => {

          // OVER 1.5
          if (
            outcome.name === "Over" &&
            outcome.point === 1.5
          ) {

            overHTML += `
              <div class="card over">
                <b>${partita}</b>
                <div>Quota ${outcome.price}</div>
              </div>
            `;
          }

          // UNDER 2.5
          if (
            outcome.name === "Under" &&
            outcome.point === 2.5
          ) {

            underHTML += `
              <div class="card under">
                <b>${partita}</b>
                <div>Quota ${outcome.price}</div>
              </div>
            `;
          }

        });

      });

    });

    document.getElementById("over").innerHTML =
      overHTML || "Nessun Over 1.5 trovato";

    document.getElementById("under").innerHTML =
      underHTML || "Nessun Under 2.5 trovato";

  }
  catch(error) {

    document.getElementById("over").innerHTML =
      "Errore API";

    document.getElementById("under").innerHTML =
      "Errore API";

    console.log(error);
  }
}

caricaDati();
``
