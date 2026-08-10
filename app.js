const API_KEY = "fbfc72a65736699d483a2c09ec4621c5";

async function caricaDati() {

  const overDiv = document.getElementById("over");
  const underDiv = document.getElementById("under");

  overDiv.innerHTML = "<p>Ricerca Over...</p>";
  underDiv.innerHTML = "<p>Ricerca Under...</p>";

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

          const quota = outcome.price;

          // UNDER 2.5 FILTRATO
          if (
            outcome.name === "Under" &&
            outcome.point === 2.5 &&
            quota <= 1.60
          ) {

            const probabilita =
              Math.round((1 / quota) * 100);

            underHTML += `
              <div class="card under">
                <div class="match">${partita}</div>
                <div class="quota">
                  Under 2.5 @ ${quota}
                </div>
                <div class="info">
                  Probabilità stimata ${probabilita}%
                </div>
              </div>
            `;
          }

          // OVER 2.5 FILTRATO
          if (
            outcome.name === "Over" &&
            outcome.point === 2.5 &&
            quota <= 1.60
          ) {

            const probabilita =
              Math.round((1 / quota) * 100);

            overHTML += `
              <div class="card over">
                <div class="match">${partita}</div>
                <div class="quota">
                  Over 2.5 @ ${quota}
                </div>
                <div class="info">
                  Probabilità stimata ${probabilita}%
                </div>
              </div>
            `;
          }

        });

      });

    });

    overDiv.innerHTML =
      overHTML || "<p>Nessun Over 2.5 trovato</p>";

    underDiv.innerHTML =
      underHTML || "<p>Nessun Under 2.5 trovato</p>";

  }
  catch(error) {

    overDiv.innerHTML =
      "<p>Errore API</p>";

    underDiv.innerHTML =
      "<p>Errore API</p>";

    console.log(error);
  }
}

caricaDati();
``
