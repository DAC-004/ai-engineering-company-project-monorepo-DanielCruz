export function linearSearchIndex<T>(
  items: T[],
  predicate: (item: T, index: number) => boolean
): number {
  if (items.length === 0) {
    return -1;
  }

  for (let index = 0; index < items.length; index += 1) {
    if (predicate(items[index], index)) {
      return index;
    }
  }

  return -1;
}

export function linearSearch<T>(
  items: T[],
  predicate: (item: T, index: number) => boolean
): T | null {
  const index = linearSearchIndex(items, predicate);
  return index === -1 ? null : items[index];
}

export function binarySearchIndexByKey<T>(
  sortedItems: T[],
  field: keyof T,
  targetValue: string | number
): number {
  if (sortedItems.length === 0) {
    return -1;
  }

  let left = 0;
  let right = sortedItems.length - 1;

  while (left <= right) {
    const middle = Math.floor((left + right) / 2);
    const middleValue = sortedItems[middle][field];

    if (middleValue === undefined || middleValue === null) {
      return -1;
    }

    let comparison = 0;

    if (typeof middleValue === 'number' && typeof targetValue === 'number') {
      comparison = middleValue - targetValue;
    } else {
      comparison = String(middleValue).localeCompare(String(targetValue));
    }

    if (comparison === 0) {
      return middle;
    }

    if (comparison < 0) {
      left = middle + 1;
    } else {
      right = middle - 1;
    }
  }

  return -1;
}

export function binarySearchByKey<T>(
  sortedItems: T[],
  field: keyof T,
  targetValue: string | number
): T | null {
  const index = binarySearchIndexByKey(sortedItems, field, targetValue);
  return index === -1 ? null : sortedItems[index];
}
