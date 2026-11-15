# Rakennusympäristön Roslyn-yhteensopivuuskorjaus

Ajopäivä: 2026-11-14 (Europe/Helsinki). Tämä kansio dokumentoi vain
rakennusympäristön korjauksen; se ei ole arvioitava AI-toiminnallisuusmuutos.
Committia tai pushausta ei tehty.

## Lähtötila ja muutos

- Alkuperäinen haara: `ju26-issue-2283`.
- Lähtöcommit: `9df83c38409c8bfad0517aebffe48211eda4a5b4`.
- Uusi haara luotiin komennolla `git switch -c junction/trust-demo`.
- Alkuperäinen haara jäi samaan committiin. Myös uuden haaran HEAD on sama,
  sillä korjaus ja evidenssi ovat commitoimattomia työpuumuutoksia.
- Työpuu oli alussa puhdas.
- Ainoa ennestään versionhallittuun tiedostoon tehty muutos on
  `Directory.Packages.props`: IsAnalyzerProject-ehdollinen
  MicrosoftCodeAnalysisVersion 4.12.0 -> 4.11.0. Katso `change.patch`.
  Ehdoton Roslyn-versio säilyy 4.12.0:ssa. Muita riippuvuuksia, testejä tai
  generoituja luokkia ei muutettu.

SDK: 8.0.428; MSBuild 17.11.71; macOS 26.5, osx-arm64.
Täysi ympäristötieto: `sdk-info.txt`. SDK:n csc-version tarkistuskomento oli
`dotnet /usr/local/share/dotnet/sdk/8.0.428/Roslyn/bincore/csc.dll -version`:
`4.11.0-3.25569.22 (3fb752d4)` (edellisen tutkimusajon havainto).

## Alkuperäiset ajot (ennen muutosta)

Edellisen tutkimusvaiheen olemassa olevat lokit kopioitiin sellaisinaan
/tmp-hakemistosta. Niitä ei tuotettu uudelleen korjauksen jälkeen.

| Komento | Exit | Todellinen tulos | Loki |
| --- | --- | --- | --- |
| `dotnet build -c Debug` | 1 | 5 varoitusta, 15 virhettä | `original/build.log` |
| `dotnet test tests/MessagePack.Tests/MessagePack.Tests.csproj -c Debug -f net8.0` | 0 | 985 läpäisi, 6 ohitettiin, 0 epäonnistui; 991 yhteensä | `original/limited-test.log` |

Kopiointilähteet: `/tmp/ju26-build-full.log` ja `/tmp/ju26-test-full.log`.
Exit-koodit perustuvat edellisen vaiheen työkalutuloksiin, eivät lokiin lisättyihin
arvoihin. Samojen komentojen alkuperäiset sandbox-yritykset on säilytetty
`original/sandbox-build.log` ja `original/sandbox-test.log`: ne eivät ole
kelvollisia projektin tarkistustuloksia. Testiyrityksessä named pipe -yhteys
estyi (Permission denied), joten varsinaiset ajot tehtiin sandboxin ulkopuolella.

**Puuttuvat alkuperäiset lokit:** käyttäjän ilmoittaman 7 varoituksen ja 15
virheen ajon lokia ei ole toimitettu. Alkuperäistä puhdasta käännösajoa,
alkuperäistä koko solutionin testiajoa ja alkuperäisiä TRX-tiedostoja ei ole.
Tässä ei väitetä niiden tuloksia tunnetuiksi.

## Uudet ajot

Komennot suoritettiin repon juuressa tässä järjestyksessä sandboxin ulkopuolella
MSBuildin ja testiprosessien yhteyksiä varten. stdout ja stderr yhdistettiin
taulukon lokiin. Mitään testisuodatinta tai tarkistusten ohitusta ei käytetty.

| Komento | Exit | Tulos | Loki |
| --- | --- | --- | --- |
| `dotnet clean MessagePack.sln -c Debug` | 0 | 0 varoitusta, 0 virhettä | `new/clean.log` |
| `dotnet build MessagePack.sln -c Debug` | 0 | 2 varoitusta, 0 virhettä | `new/build.log` |
| `dotnet test MessagePack.sln -c Debug --no-build --no-restore --logger trx --results-directory evidence/setup/new/test-results` | 0 | 1592 läpäisi, 6 ohitettiin, 0 epäonnistui; 1598 yhteensä | `new/test.log` |

Puhdas käännös tarkoittaa tässä onnistunutta solutionin Clean-kohdetta ja sitä
seuraavaa normaalia Build-kohdetta palautuksineen; NuGet-välimuistia ei tyhjennetty.
Testiajo käyttää juuri tämän käännöksen tuotoksia. Molemmat käännösvaroitukset
ovat NU1901-varoituksia NuGet.Protocol 6.8.0:sta; riippuvuutta ei muutettu.

Projektiasetukset (`project-settings.txt`, `tests/Directory.Build.props` ja
MessagePack.sln) osoittavat, että solutionissa on kahdeksan testiprojektia.
Kaikkien ajettava Mac-kohde on net8.0. MessagePack.Tests lisää net472:n vain
Windowsissa. Siksi solutionin testikomento ilman kehysylikirjoitusta kattaa
kaikki Macilla asetusten mukaan ajettavat testit. Solution sisältää myös
net472-sandbox-/benchmark-projekteja; niiden .NET Framework -suoritusta ei
yritetty eikä niitä tulkita testiprojekteiksi.

| Testiprojekti (net8.0) | Läpäisi | Ohitettiin | Epäonnistui |
| --- | ---: | ---: | ---: |
| MessagePack.Tests | 985 | 6 | 0 |
| MessagePack.Internal.Tests | 291 | 0 | 0 |
| MessagePack.AspNetCoreMvcFormatter.Tests | 6 | 0 | 0 |
| MessagePack.Experimental.Tests | 95 | 0 | 0 |
| MessagePack.GeneratedCode.Tests | 11 | 0 | 0 |
| MessagePack.SourceGenerator.ExecutionTests | 14 | 0 | 0 |
| MessagePack.SourceGenerator.MapModeExecutionTests | 20 | 0 | 0 |
| MessagePack.SourceGenerator.Tests | 170 | 0 | 0 |

TRX-raportit ovat `new/test-results`-hakemistossa. Testirunner raportoi lisäksi
kolme duplikaatti-ID:n vuoksi sivuutettua testitapausta; ne eivät ole uusia
muutoksia, ja sama ilmoitus esiintyy alkuperäisessä rajatussa ajossa. Kuusi
ohitettua testiä ovat olemassa olevia Skip-määrityksiä. Testejä ei poistettu
eikä niiden asetuksia muutettu.

## Todistettu vaikutus ja rajat

Roslyn 4.12:een viittaava generaattori ei latautunut SDK:n Roslyn 4.11 -hostiin
(CS9057), joten generoidut resolverit ja Instance-jäsenet puuttuivat.
IsAnalyzerProject koskee generaattoria, analysoijapakettiprojektia ja code fix
-projektia. Korjauksen jälkeen palautettu generaattorin project.assets.json
sisältää Microsoft.CodeAnalysis.Common/CSharp 4.11.0:n. CS9057-varoitukset ja
kaikki alkuperäiset 15 käännösvirhettä poistuivat. Puhdas solution-käännös ja
kaikki kahdeksan Mac-testiprojektia läpäisivät. Generaattori- ja code fix
-testiprojektin 4.12-riippuvuudet säilyivät ennallaan.

Tämä todistaa Debug-käännöksen ja yllä kirjatut net8.0-testit tässä Mac/SDK-
ympäristössä. Release, Windows/net472-testit, Linux, Unity/IL2CPP,
paketointi/julkaisu ja muut SDK-/IDE-versiot jäivät tarkistamatta. Ohitetut ja
duplikaatti-ID:n vuoksi sivuutetut testit eivät ole todiste niiden toimivuudesta.
Arvioitavan AI-muutoksen toimivuutta ei arvioitu eikä sitä toteutettu tässä.
