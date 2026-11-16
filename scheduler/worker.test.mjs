import { test } from "node:test";
import assert from "node:assert/strict";
import { dispatch } from "./worker.mjs";

const env = {GITHUB_TOKEN:"test-only"};
function mock(runs = [{status:"completed",conclusion:"success"}], status=204) {
  const calls=[];
  const fetcher=async(url,init)=>{
    calls.push({url,init});
    assert.ok(url.startsWith("https://api.github.com/"), "only talks to GitHub");
    if(url.includes("/runs?")) return Response.json({workflow_runs:runs});
    return new Response(null,{status});
  };
  return {calls,fetcher};
}
test("idle repo gets exactly one dispatch on main",async()=>{
  const m=mock();
  assert.equal(await dispatch(env,m.fetcher),"dispatched");
  const posts=m.calls.filter(c=>c.init.method==="POST");
  assert.equal(posts.length,1);
  assert.deepEqual(JSON.parse(posts[0].init.body),{ref:"main",inputs:{probe:false}});
});
test("active runs and recent failures do not create more runs",async()=>{
  for(const [run,expected] of [
    [{status:"queued"},"active"],
    [{status:"in_progress"},"active"],
    [{status:"completed",conclusion:"failure",updated_at:new Date().toISOString()},"retry-cooldown"],
  ]){
    const m=mock([run]);
    assert.equal(await dispatch(env,m.fetcher),expected);
    assert.equal(m.calls.length,1);
  }
});
test("an old failure no longer blocks the next run",async()=>{
  const m=mock([{status:"completed",conclusion:"failure",updated_at:new Date(Date.now()-20*60000).toISOString()}]);
  assert.equal(await dispatch(env,m.fetcher),"dispatched");
});
test("missing token and dispatch errors are visible",async()=>{
  await assert.rejects(dispatch({}),/Missing/);
  await assert.rejects(dispatch(env,mock(undefined,403).fetcher),/403/);
});
