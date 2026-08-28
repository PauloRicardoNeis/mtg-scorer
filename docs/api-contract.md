# Product API contract

The first product slice exposes Python-published card scores through Spring Boot.
All routes are versioned under `/api/v1`.

## Search cards

```http
GET /api/v1/cards?query=engine&set=eng&rarity=rare&sort=buildaround&limit=24
```

| Parameter | Default | Semantics |
| --- | --- | --- |
| `query` | empty | Case-insensitive substring of the Oracle card name |
| `set` | empty | Printing set code; combined with rarity on the same printing |
| `rarity` | empty | `common`, `uncommon`, `rare`, or `mythic` |
| `sort` | `BUILDAROUND` | `STAPLE`, `BUILDAROUND`, `EVIDENCE`, or `DISTINCTIVENESS`; case-insensitive |
| `limit` | `24` | Result count from 1 through 100 |

The response contains:

- `contractVersion` and `catalogKind`;
- complete dataset, feature-pipeline, score-model, and configuration identity;
- the total matching count before the limit;
- Oracle cards with printing filters, score coordinates, feature coverage, and
  human-facing reasons.

`catalogKind=DEMONSTRATION` means the observations are synthetic contract fixtures,
not historical claims. Product surfaces must preserve that label.

## Fetch one Oracle card

```http
GET /api/v1/cards/{oracleId}
```

The route returns the published card or `404` when the Oracle ID is absent from the
selected snapshot.

## Runtime boundary

The bundled demonstration catalog lives at
`classpath:catalog/demo-card-scores.json`. A deployment can override
`mtg-scorer.catalog.resource` with another Spring `Resource` URI. This adapter is
temporary: an empirical deployment will read versioned PostgreSQL gold tables
behind the same repository interface.

The Next.js server reads the API base URL from `MTG_SCORER_API_URL`. Browser code
does not connect to the database, Parquet, DuckDB, or an external MTG source.
