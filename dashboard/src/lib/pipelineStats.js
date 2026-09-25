export function computePipelineStats(data) {
  const sm = data?.sitemaps || {};
  const pl = data?.pipeline || {};

  const pipelineTotal = pl.total_tracked || 0;
  const pipelineIndexed = pl.indexed || 0;
  const pipelineNotIndexed = pl.not_indexed || 0;
  const pipelineRate = pipelineTotal > 0 ? (pipelineIndexed / pipelineTotal * 100).toFixed(1) : 0;
  const totalSubmitted = sm.total_submitted || 0;
  const scanPct = totalSubmitted > 0 ? (pipelineTotal / totalSubmitted * 100).toFixed(1) : 0;

  return { pipelineTotal, pipelineIndexed, pipelineNotIndexed, pipelineRate, totalSubmitted, scanPct };
}
