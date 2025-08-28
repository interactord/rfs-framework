"""
Unit tests for HOF Collections module

Tests Swift-inspired collection operations and functional utilities.
"""

import pytest

from rfs.hof.collections import (
    chunk,
    compact_map,
    drop,
    drop_first,
    drop_last,
    drop_while,
    filter_indexed,
    first,
    flat_map,
    flatten,
    fold,
    fold_left,
    fold_right,
    forEach,
    group_by,
    last,
    map_indexed,
    merging,
    partition,
    reduce_indexed,
    scan,
    take,
    take_while,
    zip_with,
)


class TestSwiftInspiredFunctions:
    """Test Swift-inspired collection functions."""

    def test_first(self):
        """Test first function."""
        # Without predicate
        assert first([1, 2, 3]) == 1
        assert first([]) is None

        # With predicate
        assert first([1, 2, 3, 4, 5], lambda x: x > 3) == 4
        assert first([1, 2, 3], lambda x: x > 10) is None

    def test_last(self):
        """Test last function."""
        # Without predicate
        assert last([1, 2, 3]) == 3
        assert last([]) is None

        # With predicate
        assert last([1, 2, 3, 4, 5], lambda x: x < 4) == 3
        assert last([1, 2, 3], lambda x: x > 10) is None

    def test_compact_map(self):
        """Test compact_map function."""
        # Filter None values
        result = compact_map(lambda x: x if x > 2 else None, [1, 2, 3, 4])
        assert result == [3, 4]

        # Transform and filter
        result = compact_map(lambda x: x**2 if x % 2 == 0 else None, [1, 2, 3, 4, 5, 6])
        assert result == [4, 16, 36]

    def test_flat_map(self):
        """Test flat_map function."""
        # Duplicate each element
        result = flat_map(lambda x: [x, x * 2], [1, 2, 3])
        assert result == [1, 2, 2, 4, 3, 6]

        # Generate ranges
        result = flat_map(lambda x: range(x), [1, 2, 3])
        assert result == [0, 0, 1, 0, 1, 2]

    def test_drop_last(self):
        """Test drop_last function."""
        # Drop n elements
        assert drop_last([1, 2, 3, 4, 5], 2) == [1, 2, 3]
        assert drop_last([1, 2], 5) == []

        # Drop with predicate
        assert drop_last([1, 2, 3, 4, 5], predicate=lambda x: x > 3) == [1, 2, 3]
        assert drop_last([5, 4, 3, 2, 1], predicate=lambda x: x <= 3) == [5, 4]

    def test_drop_first(self):
        """Test drop_first function."""
        # Drop n elements
        assert drop_first([1, 2, 3, 4, 5], 2) == [3, 4, 5]
        assert drop_first([1, 2], 5) == []

        # Drop with predicate
        assert drop_first([1, 2, 3, 4, 5], predicate=lambda x: x < 3) == [3, 4, 5]
        assert drop_first([5, 4, 3, 2, 1], predicate=lambda x: x > 3) == [3, 2, 1]

    def test_merging(self):
        """Test merging dictionaries with conflict resolution."""
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 3, "c": 4}

        # Keep new value
        result = merging(d1, d2, lambda old, new: new)
        assert result == {"a": 1, "b": 3, "c": 4}

        # Sum values
        result = merging(d1, d2, lambda old, new: old + new)
        assert result == {"a": 1, "b": 5, "c": 4}

        # Keep old value
        result = merging(d1, d2, lambda old, new: old)
        assert result == {"a": 1, "b": 2, "c": 4}


class TestIndexedOperations:
    """Test indexed collection operations."""

    def test_map_indexed(self):
        """Test map_indexed function."""
        result = map_indexed(lambda i, x: f"{i}:{x}", ["a", "b", "c"])
        assert result == ["0:a", "1:b", "2:c"]

    def test_filter_indexed(self):
        """Test filter_indexed function."""
        # Filter even indices
        result = filter_indexed(lambda i, x: i % 2 == 0, ["a", "b", "c", "d"])
        assert result == ["a", "c"]

        # Filter based on value and index
        result = filter_indexed(lambda i, x: i > 0 and x > 2, [1, 2, 3, 4])
        assert result == [3, 4]

    def test_reduce_indexed(self):
        """Test reduce_indexed function."""
        # Sum with index weighting
        result = reduce_indexed(lambda i, acc, x: acc + i * x, [1, 2, 3], 0)
        assert result == 8  # 0*1 + 1*2 + 2*3


class TestFoldOperations:
    """Test fold operations."""

    def test_fold(self):
        """Test fold function."""
        result = fold(lambda acc, x: acc + x, 0, [1, 2, 3, 4])
        assert result == 10

        result = fold(lambda acc, x: acc * x, 1, [1, 2, 3, 4])
        assert result == 24

    def test_fold_left(self):
        """Test fold_left function."""
        result = fold_left(lambda acc, x: acc - x, 10, [1, 2, 3])
        assert result == 4  # ((10 - 1) - 2) - 3

    def test_fold_right(self):
        """Test fold_right function."""
        result = fold_right(lambda x, acc: f"({x}{acc})", "", ["a", "b", "c"])
        assert result == "(a(b(c)))"

    def test_scan(self):
        """Test scan function."""
        result = scan(lambda acc, x: acc + x, 0, [1, 2, 3, 4])
        assert result == [0, 1, 3, 6, 10]

        result = scan(lambda acc, x: acc * x, 1, [2, 3, 4])
        assert result == [1, 2, 6, 24]


class TestPartitioningAndGrouping:
    """Test partitioning and grouping operations."""

    def test_partition(self):
        """Test partition function."""
        evens, odds = partition(lambda x: x % 2 == 0, [1, 2, 3, 4, 5])
        assert evens == [2, 4]
        assert odds == [1, 3, 5]

    def test_group_by(self):
        """Test group_by function."""
        result = group_by(lambda x: x % 3, [1, 2, 3, 4, 5, 6])
        assert result == {1: [1, 4], 2: [2, 5], 0: [3, 6]}

        # Group strings by length
        result = group_by(len, ["a", "bb", "ccc", "dd", "e"])
        assert result == {1: ["a", "e"], 2: ["bb", "dd"], 3: ["ccc"]}

    def test_chunk(self):
        """Test chunk function."""
        result = chunk([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

        result = chunk(range(10), 3)
        assert result == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


class TestCollectionUtilities:
    """Test collection utility functions."""

    def test_flatten(self):
        """Test flatten function."""
        result = flatten([[1, 2], [3, 4], [5]])
        assert result == [1, 2, 3, 4, 5]

        result = flatten([["a"], ["b", "c"], [], ["d"]])
        assert result == ["a", "b", "c", "d"]

    def test_zip_with(self):
        """Test zip_with function."""
        result = zip_with(lambda x, y: x + y, [1, 2, 3], [10, 20, 30])
        assert result == [11, 22, 33]

        result = zip_with(lambda x, y, z: x * y + z, [1, 2, 3], [2, 3, 4], [10, 10, 10])
        assert result == [12, 16, 22]

    def test_take(self):
        """Test take function."""
        assert take(3, [1, 2, 3, 4, 5]) == [1, 2, 3]
        assert take(10, [1, 2, 3]) == [1, 2, 3]
        assert take(0, [1, 2, 3]) == []

    def test_drop(self):
        """Test drop function."""
        assert drop(2, [1, 2, 3, 4, 5]) == [3, 4, 5]
        assert drop(10, [1, 2, 3]) == []
        assert drop(0, [1, 2, 3]) == [1, 2, 3]

    def test_take_while(self):
        """Test take_while function."""
        result = take_while(lambda x: x < 4, [1, 2, 3, 4, 5])
        assert result == [1, 2, 3]

        result = take_while(lambda x: x > 0, [1, -1, 2, 3])
        assert result == [1]

    def test_drop_while(self):
        """Test drop_while function."""
        result = drop_while(lambda x: x < 3, [1, 2, 3, 4, 5])
        assert result == [3, 4, 5]

        result = drop_while(lambda x: x > 0, [1, 2, -1, 3])
        assert result == [-1, 3]


class TestSwiftForEach:
    """Test Swift-style forEach function."""

    def test_forEach_basic_side_effects(self):
        """Test basic forEach with side effects."""
        result = []
        forEach(lambda x: result.append(x * 2), [1, 2, 3])
        assert result == [2, 4, 6]

    def test_forEach_empty_iterable(self):
        """Test forEach with empty iterable."""
        result = []
        forEach(lambda x: result.append(x), [])
        assert result == []

    def test_forEach_string_processing(self):
        """Test forEach with string processing."""
        processed = []
        forEach(lambda s: processed.append(s.upper()), ["hello", "world"])
        assert processed == ["HELLO", "WORLD"]

    def test_forEach_dictionary_updates(self):
        """Test forEach updating a dictionary."""
        data = {}
        items = [{"id": 1, "value": "A"}, {"id": 2, "value": "B"}, {"id": 3, "value": "C"}]
        forEach(lambda item: data.update({item["id"]: item["value"]}), items)
        assert data == {1: "A", 2: "B", 3: "C"}

    def test_forEach_complex_side_effects(self):
        """Test forEach with complex side effects."""
        # 통계를 누적하는 예시
        stats = {"total": 0, "count": 0, "max": float("-inf")}
        
        def accumulate_stats(value):
            stats["total"] += value
            stats["count"] += 1
            stats["max"] = max(stats["max"], value)
        
        forEach(accumulate_stats, [5, 2, 8, 1, 9])
        
        assert stats["total"] == 25
        assert stats["count"] == 5
        assert stats["max"] == 9

    def test_forEach_nested_data_processing(self):
        """Test forEach with nested data structures."""
        flattened = []
        nested_lists = [[1, 2], [3, 4, 5], [6]]
        
        forEach(lambda lst: forEach(lambda x: flattened.append(x), lst), nested_lists)
        assert flattened == [1, 2, 3, 4, 5, 6]

    def test_forEach_with_enumerate_pattern(self):
        """Test forEach pattern similar to enumerate."""
        indexed_items = []
        items = ["apple", "banana", "cherry"]
        
        # forEach를 사용하여 인덱스와 함께 처리
        for i, item in enumerate(items):
            forEach(lambda _: indexed_items.append(f"{i}: {item}"), [item])
        
        assert len(indexed_items) == 3
        assert "0: apple" in indexed_items
        assert "2: cherry" in indexed_items

    def test_forEach_return_value(self):
        """Test that forEach returns None."""
        result = forEach(lambda x: x * 2, [1, 2, 3])
        assert result is None

    def test_forEach_with_print_simulation(self):
        """Test forEach with print-like operations (captured)."""
        output = []
        
        def mock_print(text):
            output.append(str(text))
        
        forEach(lambda x: mock_print(f"Processing: {x}"), ["a", "b", "c"])
        
        assert output == ["Processing: a", "Processing: b", "Processing: c"]

    def test_forEach_type_conversion(self):
        """Test forEach with type conversions."""
        converted = []
        numbers = ["1", "2", "3", "4", "5"]
        
        forEach(lambda s: converted.append(int(s) * 10), numbers)
        assert converted == [10, 20, 30, 40, 50]

    def test_forEach_generator_input(self):
        """Test forEach with generator input."""
        result = []
        
        def number_generator():
            for i in range(3):
                yield i * 2
        
        forEach(lambda x: result.append(x + 1), number_generator())
        assert result == [1, 3, 5]
