package io.mtgscorer.api.error;

public final class CatalogProblem extends RuntimeException {
  private final int status;
  private final String code;

  public CatalogProblem(int status, String code, String detail) {
    super(detail);
    this.status = status;
    this.code = code;
  }

  public int status() {
    return status;
  }

  public String code() {
    return code;
  }

  public static CatalogProblem query(String detail) {
    return new CatalogProblem(400, "invalid_query", detail);
  }

  public static CatalogProblem cursor() {
    return new CatalogProblem(400, "invalid_cursor", "The cursor does not match this request.");
  }
}
