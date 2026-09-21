"""Domain errors for the HealthCore sales-forecast pipeline."""


class SalesForecastError(ValueError):
    """Base error for dataset, split, metric, or variability failures."""


class DatasetValidationError(SalesForecastError):
    """The supplied sales CSV does not match the HealthCore contract."""


class VariabilityEstimationError(SalesForecastError):
    """Training-only out-of-sample residual variability cannot be estimated."""


class MetricComputationError(SalesForecastError):
    """A required metric cannot be computed from the available sample."""
