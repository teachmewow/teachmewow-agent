from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)
_BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_BASE64_LOOKUP = {char: idx for idx, char in enumerate(_BASE64_ALPHABET)}


@dataclass
class DecodedNode:
    node_id: int
    ranks_purchased: int
    choice_entry_index: int | None


def decode_import_code(
    import_code: str, tree_snapshot: dict | None, debug: bool = False
) -> list[str]:
    """
    Decode a Blizzard talent import string into a list of selected node ids.
    Placeholder for the official decoding algorithm.
    """
    if not import_code or not tree_snapshot:
        return []
    decoded = decode_import_code_nodes(import_code, tree_snapshot, debug=debug)
    return [str(node.node_id) for node in decoded]


def decode_import_code_nodes(
    import_code: str, tree_snapshot: dict | None, debug: bool = False
) -> list[DecodedNode]:
    """
    Decode a Blizzard talent import string into node selections with rank metadata.
    """
    if not import_code or not tree_snapshot:
        return []
    node_meta = _extract_tree_node_meta(tree_snapshot, debug=debug)
    if not node_meta:
        return []
    stream = _ImportDataStream(import_code)
    if stream.get_number_of_bits() < 8 + 16 + 128:
        return []
    serialization_version = stream.extract_value(8)
    spec_id = stream.extract_value(16)
    _tree_hash = [stream.extract_value(8) for _ in range(16)]
    if debug:
        logger.info(
            "decode_import_code_nodes version=%s spec_id=%s total_nodes=%s bits=%s",
            serialization_version,
            spec_id,
            len(node_meta),
            stream.get_number_of_bits() - stream.bit_index,
        )
    decoded = _read_loadout_content(
        stream,
        node_meta,
        serialization_version=serialization_version,
        debug=debug,
    )
    if debug:
        logger.info(
            "decode_import_code_nodes selected=%s remaining_bits=%s",
            len(decoded),
            stream.get_number_of_bits() - stream.bit_index,
        )
    return decoded


def _read_loadout_content(
    stream: _ImportDataStream,
    node_meta: list[tuple[int, int]],
    serialization_version: int,
    debug: bool = False,
) -> list[DecodedNode]:
    results: list[DecodedNode] = []
    for node_id, max_rank in node_meta:
        before = stream.bit_index
        is_selected = stream.extract_value(1) == 1
        if not is_selected:
            continue
        is_purchased = True
        is_partially_ranked = False
        ranks_purchased = max_rank
        is_choice_node = False
        choice_entry_index = None
        if serialization_version >= 2:
            is_purchased = stream.extract_value(1) == 1
            if is_purchased:
                is_partially_ranked = stream.extract_value(1) == 1
                if is_partially_ranked:
                    ranks_purchased = stream.extract_value(6)
                is_choice_node = stream.extract_value(1) == 1
                if is_choice_node:
                    choice_entry_index = stream.extract_value(2)
            else:
                # Granted nodes are selected but not purchased; treat as fully active.
                ranks_purchased = max_rank
        else:
            is_partially_ranked = stream.extract_value(1) == 1
            if is_partially_ranked:
                ranks_purchased = stream.extract_value(6)
            else:
                ranks_purchased = max_rank
            is_choice_node = stream.extract_value(1) == 1
            if is_choice_node:
                choice_entry_index = stream.extract_value(2)
        if max_rank > 0 and ranks_purchased > max_rank:
            ranks_purchased = max_rank
        if debug and ranks_purchased == 0:
            logger.info(
                "decoded node=%s has zero rank (max=%s) bits=%s->%s",
                node_id,
                max_rank,
                before,
                stream.bit_index,
            )
        if debug:
            logger.info(
                "decoded node=%s rank=%s max=%s purchased=%s choice=%s bits=%s->%s",
                node_id,
                ranks_purchased,
                max_rank,
                is_purchased,
                choice_entry_index,
                before,
                stream.bit_index,
            )
        results.append(
            DecodedNode(
                node_id=node_id,
                ranks_purchased=ranks_purchased,
                choice_entry_index=choice_entry_index,
            )
        )
    return results


def _extract_tree_node_meta(
    tree_snapshot: dict, debug: bool = False
) -> list[tuple[int, int]]:
    ordered_nodes = _extract_ordered_nodes(tree_snapshot, debug=debug)
    node_meta: list[tuple[int, int]] = []
    seen: set[int] = set()
    for node in ordered_nodes:
        node_id = node.get("id") if isinstance(node, dict) else None
        if not isinstance(node_id, int) or node_id in seen:
            continue
        max_rank = _extract_max_rank(node)
        node_meta.append((node_id, max_rank))
        seen.add(node_id)
    return node_meta


def _extract_ordered_nodes(tree_snapshot: dict, debug: bool = False) -> list[dict]:
    nodes = tree_snapshot.get("talent_nodes") or []
    if isinstance(nodes, list) and nodes:
        return sorted(
            [node for node in nodes if isinstance(node, dict)],
            key=lambda node: int(node.get("id", 0) or 0),
        )
    nodes = tree_snapshot.get("nodes") or []
    if isinstance(nodes, list) and nodes:
        return sorted(
            [node for node in nodes if isinstance(node, dict)],
            key=lambda node: int(node.get("id", 0) or 0),
        )
    if debug:
        logger.warning(
            "Tree snapshot lacks global node list; decoding may be incomplete."
        )
    combined_nodes: list[dict] = []
    for key in ("class_talent_nodes", "spec_talent_nodes"):
        raw_nodes = tree_snapshot.get(key) or []
        if isinstance(raw_nodes, list):
            combined_nodes.extend([node for node in raw_nodes if isinstance(node, dict)])
    hero_trees = tree_snapshot.get("hero_talent_trees") or []
    for hero_tree in hero_trees:
        hero_nodes = (
            hero_tree.get("hero_talent_nodes") if isinstance(hero_tree, dict) else None
        )
        if isinstance(hero_nodes, list):
            combined_nodes.extend([node for node in hero_nodes if isinstance(node, dict)])
    return sorted(combined_nodes, key=lambda node: int(node.get("id", 0) or 0))


def _extract_max_rank(node: dict) -> int:
    max_rank = node.get("max_ranks")
    if isinstance(max_rank, int) and max_rank > 0:
        return max_rank
    ranks = node.get("ranks") if isinstance(node, dict) else None
    if isinstance(ranks, list) and ranks:
        return len(ranks)
    return 1


class _ImportDataStream:
    def __init__(self, import_string: str) -> None:
        self.data_values = self._convert_from_base64(import_string)
        self.current_index = 0
        self.current_extracted_bits = 0
        self.current_remaining_value = (
            self.data_values[0] if self.data_values else 0
        )
        self._bit_index = 0

    def _convert_from_base64(self, export_string: str) -> list[int]:
        values: list[int] = []
        for ch in export_string.strip():
            if ch not in _BASE64_LOOKUP:
                continue
            values.append(_BASE64_LOOKUP[ch])
        return values

    def get_number_of_bits(self) -> int:
        return 6 * len(self.data_values)

    @property
    def bit_index(self) -> int:
        return self._bit_index

    def extract_value(self, bit_width: int) -> int:
        if self.current_index >= len(self.data_values):
            return 0
        value = 0
        bits_needed = bit_width
        extracted_bits = 0
        while bits_needed > 0:
            remaining_bits = 6 - self.current_extracted_bits
            bits_to_extract = remaining_bits if remaining_bits < bits_needed else bits_needed
            self.current_extracted_bits += bits_to_extract
            max_storable_value = 1 << bits_to_extract
            remainder = self.current_remaining_value % max_storable_value
            self.current_remaining_value //= max_storable_value
            value += remainder << extracted_bits
            extracted_bits += bits_to_extract
            bits_needed -= bits_to_extract
            self._bit_index += bits_to_extract
            if bits_to_extract < remaining_bits:
                break
            self.current_index += 1
            self.current_extracted_bits = 0
            if self.current_index < len(self.data_values):
                self.current_remaining_value = self.data_values[self.current_index]
        return value
