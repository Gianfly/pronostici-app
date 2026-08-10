function caricaDati() {

const overData = [
{match:"Milan - Como", prob:89},
{match:"Arsenal - Leeds", prob:87},
{match:"PSV - Utrecht", prob:85}
];

const underData = [
{match:"Torino - Udinese", prob:81},
{match:"Getafe - Osasuna", prob:79},
{match:"Bari - Palermo", prob:75}
];

document.getElementById("over").innerHTML =
overData.map(x => `
<div class="card over">
<b>${x.match}</b>
<div class="percent">${x.prob}%</div>
</div>
`).join("");

document.getElementById("under").innerHTML =
underData.map(x => `
<div class="card under">
<b>${x.match}</b>
<div class="percent">${x.prob}%</div>
</div>
`).join("");
}

caricaDati();
