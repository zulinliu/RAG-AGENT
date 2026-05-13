from __future__ import annotations

from rag_qa.retrieval.retriever import RetrievedChunk


class RRFFusion:
    def __init__(self, k: int = 60) -> None:
        self._k = k

    def fuse(self, result_lists: list[list[RetrievedChunk]]) -> list[RetrievedChunk]:
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievedChunk] = {}

        for result_list in result_lists:
            for rank, chunk in enumerate(result_list, start=1):
                cid = chunk.chunk_id
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (self._k + rank)
                if cid not in chunk_map:
                    chunk_map[cid] = chunk

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        results: list[RetrievedChunk] = []
        for cid in sorted_ids:
            chunk = chunk_map[cid].model_copy(update={
                "score": rrf_scores[cid],
                "source": "rrf_fusion",
            })
            results.append(chunk)
        return results
