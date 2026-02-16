# EON Next GraphQL Entities and Edges

This document maps the key GraphQL entities, nested relationships (edges), and fields seen in the HAR and used by this project.

## Scope

Primary operations currently used in the client:

- `loginEmailAuthentication`
- `getUserAccounts`
- `smartDevicesForAccount`
- `balanceForDevice`

Related operations observed in HAR (useful for future parsing):

- `UserContext`
- `getLoggedInUser`
- `getAccountOverview`
- `accountOverviewBase`
- `accountOverviewHeader`
- `stripeBannersAccount`
- `GetOptimizelyAttributeUserData`
- `smartPaygAccountSetupPanel`
- `tariffs`
- `meterReadingsDue`
- `isSmartMeterCommunicatingHook`
- `getAccountDetailsSmartHalfHourlyPage`

---

## 1) Authentication Graph

### Operation: `loginEmailAuthentication`

Mutation root:

- `obtainKrakenToken`
  - `payload`
  - `refreshExpiresIn`
  - `refreshToken`
  - `token`

### Parsing notes

- `token` is the access token used in the `authorization` request header.
- Token expiry is read from JWT `exp` claim for local cache freshness checks.

---

## 2) Account Discovery Graph

### Operation: `getUserAccounts`

Query root:

- `viewer`
  - `id`
  - `email`
  - `accounts` (list; polymorphic with `... on AccountType`)
    - `id`
    - `number` (account number, e.g. `A-...`)
    - `accountType`
    - `balance`
    - `properties` (list)
      - `id`
      - `address`

### Entity/edge view

- `Viewer`
  - `accounts[] -> AccountType`
    - `properties[] -> PropertyType`

### Parsing notes

- For smart PAYG, `AccountType.balance` can be `0` even when live credit exists.
- `number` is the key account identifier used in downstream queries.

---

## 3) Smart Device Discovery Graph

### Operation: `smartDevicesForAccount`

Query root:

- `account(accountNumber: $account)`
  - `id`
  - `properties` (list)
    - `electricityMeterPoints` (list)
      - `id`
      - `mpan`
      - `targetSsd`
      - `meters` (list)
        - `id`
        - `smartDevices` (list)
          - `deviceId`
          - `weeklyDebtRecoveryRateInPence`
    - `gasMeterPoints` (list)
      - `id`
      - `mprn`
      - `targetSsd`
      - `meters` (list)
        - `id`
        - `smartDevices` (list)
          - `deviceId`
          - `weeklyDebtRecoveryRateInPence`

### Entity/edge view

- `AccountType`
  - `properties[] -> PropertyType`
    - `electricityMeterPoints[] -> ElectricityMeterPointType`
      - `meters[] -> ElectricityMeterType`
        - `smartDevices[] -> SmartMeterDeviceType`
    - `gasMeterPoints[] -> GasMeterPointType`
      - `meters[] -> GasMeterType`
        - `smartDevices[] -> SmartMeterDeviceType`

### Parsing notes

- Live prepay balance lookup depends on `smartDevices[].deviceId`.
- Typical parser path:
  - account -> first property -> first electricity meter point -> first meter -> first smart device -> `deviceId`

---

## 4) Live Prepay Balance Graph

### Operation: `balanceForDevice`

Query root:

- `prepayBalanceSnapshot(deviceId: $deviceId)`
  - `asAt`
  - `creditInPence`
  - `debtInPence`

### Parsing notes

- `creditInPence` is the value to use for smart PAYG live credit.
- Convert to GBP with:
  - `credit_gbp = creditInPence / 100`
- Example observed value:
  - `creditInPence: 19059` -> `190.59`

---

## 5) Connection/Edge Pattern in Kraken GraphQL

Many fields use Relay-like connection objects:

- `<field>(first: N) -> { edges: [{ node: ... }], pageInfo: ... }`

Common examples seen in HAR:

- `applications(first: 1) { edges { node { ... } } }`
- `directDebitInstructions(first: ...) { edges { node { ... } } }`
- `transactions(first: ...) { edges { node { ... } } }`

### Parsing guidance

- Treat missing/empty `edges` as valid (not errors).
- Always null-check each level: connection -> edges -> node.

---

## 6) Recommended Parse Order for Balance

1. Authenticate (`loginEmailAuthentication`) and set token.
2. Get account number (`getUserAccounts`).
3. Read `AccountType.balance` from the selected account.
4. If `balance == 0` and account appears smart PAYG:
   1. Resolve `deviceId` via `smartDevicesForAccount`.
   2. Read `creditInPence` via `balanceForDevice`.
   3. Convert pence -> GBP for display.

---

## 7) Error Handling Expectations

GraphQL response envelope:

- Success: `{ "data": { ... } }`
- Failure: `{ "errors": [ ... ] }` (may still include partial `data`)

Parser should:

- Fail fast on `errors` for critical operations (auth, account lookup, balance lookup).
- Validate expected object/list types before traversal.

---

## 8) Security Notes

- Do not persist passwords.
- If caching tokens, cache only token + expiry metadata.
- Assume HAR files can contain sensitive material (tokens, identifiers, credentials).

---

## 9) Tariff Extraction (Confirmed Path)

### Operation: `tariffs`

Query root:

- `account(accountNumber: $accountNumber)`
  - `properties`
    - `electricityMeterPoints`
      - `agreements`
        - `tariff` (polymorphic)
          - common:
            - `displayName`
            - `productCode`
            - `standingCharge`
            - `preVatStandingCharge`
          - by tariff type:
            - `StandardTariff`: `unitRate`, `preVatUnitRate`
            - `PrepayTariff`: `unitRate`, `preVatUnitRate`
            - `DayNightTariff`: `dayRate`, `nightRate`, `preVatDayRate`, `preVatNightRate`
            - `ThreeRateTariff`: `dayRate`, `nightRate`, `offPeakRate`, etc.
            - `HalfHourlyTariff`: `unitRates[] { validFrom, validTo, value }`
    - `gasMeterPoints`
      - `agreements`
        - `tariff`
          - `displayName`
          - `productCode`
          - `standingCharge`
          - `unitRate`

### Entity/edge view

- `AccountType`
  - `properties[] -> PropertyType`
    - `electricityMeterPoints[] -> ElectricityMeterPointType`
      - `agreements[] -> ElectricityAgreementType`
        - `tariff -> TariffType | DayNightTariff | StandardTariff | ...`
    - `gasMeterPoints[] -> GasMeterPointType`
      - `agreements[] -> GasAgreementType`
        - `tariff -> TariffType | StandardTariff | ...`

### Parsing notes

- For smart PAYG with Economy 7 style pricing, use `DayNightTariff` fields.
- App-observed values align with this structure:
  - tariff: `Next Flex Smart PAYG`
  - day: `31.09`
  - night: `16.42`
  - standing charge: `49.56`
- Prefer most recent active agreement (`validTo == null`, or latest `validFrom`).

---

## 10) Usage Data Availability (Derivation Path)

There is no single guaranteed `usage` scalar in the captured calls, but usage is available/derivable from meter reading edges.

### Operation: `meterReadingsDue`

Query root includes:

- `account -> properties -> electricityMeterPoints -> meters -> readings(first: 10) -> edges -> node`
- `account -> properties -> gasMeterPoints -> meters -> readings(first: 10) -> edges -> node`

`node` includes:

- `id`
- `readAt`
- `source`
- `registers` (includes flags like `isQuarantined`)

### Operation: `isSmartMeterCommunicatingHook`

Similar shape, but with deeper history:

- `...meters(includeInactive: false) -> readings(first: 100) -> edges -> node`

### Operation: `getAccountDetailsSmartHalfHourlyPage`

Useful companion data:

- `smartMeterDataPreferences(accountNumber: ...)`
  - `readingFrequency`
  - `readingsAnalysisConsentProvided`

### Usage derivation notes

- Usage is typically derived from successive register reads over time:
  - group by meter/register,
  - sort by `readAt`,
  - compute delta between adjacent readings,
  - aggregate by day/week/month.
- Exclude quarantined/invalid readings (`registers.isQuarantined`) where relevant.
- For day/night tariffs, compute per-register deltas separately before totalizing.