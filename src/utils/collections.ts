export type SortDirection = 'asc' | 'desc';

export function filterByCriteria<T>(
  items: T[],
  criteria: Partial<Record<keyof T, string>>
): T[] {
  if (items.length === 0) {
    return [];
  }

  const activeCriteria = Object.entries(criteria).filter(
    ([, value]) => value !== undefined && value !== ''
  );

  if (activeCriteria.length === 0) {
    return [...items];
  }

  return items.filter((item) =>
    activeCriteria.every(([field, expectedValue]) => {
      const actualValue = item[field as keyof T];
      return String(actualValue) === String(expectedValue);
    })
  );
}

export function sortByField<T>(
  items: T[],
  field: keyof T,
  direction: SortDirection = 'asc'
): T[] {
  if (items.length === 0) {
    return [];
  }

  const sorted = [...items].sort((left, right) => {
    const leftValue = left[field];
    const rightValue = right[field];

    if (leftValue === rightValue) {
      return 0;
    }

    if (leftValue === undefined || leftValue === null) {
      return 1;
    }

    if (rightValue === undefined || rightValue === null) {
      return -1;
    }

    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      return direction === 'asc' ? leftValue - rightValue : rightValue - leftValue;
    }

    const leftText = String(leftValue);
    const rightText = String(rightValue);
    const comparison = leftText.localeCompare(rightText);
    return direction === 'asc' ? comparison : -comparison;
  });

  return sorted;
}

export function sortByMultipleFields<T>(
  items: T[],
  fields: Array<{ field: keyof T; direction?: SortDirection }>
): T[] {
  if (items.length === 0 || fields.length === 0) {
    return [...items];
  }

  return [...items].sort((left, right) => {
    for (const { field, direction = 'asc' } of fields) {
      const leftValue = left[field];
      const rightValue = right[field];

      if (leftValue === rightValue) {
        continue;
      }

      if (leftValue === undefined || leftValue === null) {
        return 1;
      }

      if (rightValue === undefined || rightValue === null) {
        return -1;
      }

      let comparison = 0;

      if (typeof leftValue === 'number' && typeof rightValue === 'number') {
        comparison = leftValue - rightValue;
      } else {
        comparison = String(leftValue).localeCompare(String(rightValue));
      }

      return direction === 'asc' ? comparison : -comparison;
    }

    return 0;
  });
}

export function groupByField<T>(
  items: T[],
  field: keyof T
): Record<string, T[]> {
  if (items.length === 0) {
    return {};
  }

  return items.reduce<Record<string, T[]>>((groups, item) => {
    const key = String(item[field] ?? 'unknown');
    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(item);
    return groups;
  }, {});
}
