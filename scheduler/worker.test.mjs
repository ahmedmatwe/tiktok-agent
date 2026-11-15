import { test } from "node:test";
import assert from "node:assert/strict";
import { dispatch, accounts } from "./worker.mjs";

const env = {GITHUB_TOKEN:"test-only", TIKTOK_USERNAMES:"one,two"};
const id = "7705520919602679047";
function mock(state, pages, runs = [{status:"completed",conclusion:"success"}], status=204) {
  const calls=[];
  const fetcher=async(url,init)=>{
    calls.push({url,init});
    if(url.includes("/runs?")) return Response.json({workflow_runs:runs});
    if(url.includes("/contents/")) return Response.json(state);
    if(url.includes("tiktok.com")) {
      assert.equal(init.headers.Authorization,undefined);
      return new Response(pages[url.split("@")[1]] || "",{status:200});
    }
    return new Response(null,{status});
  };
  return {calls,fetcher};
}
test("multiple sources trigger one dispatch and never leak credentials",async()=>{
  const m=mock({"__initialized__:one":{done:true},"__initialized__:two":{done:true}},
    {one:"/video/"+id,two:"/video/"+id});
  assert.equal(await dispatch(env,m.fetcher),"dispatched");
  const posts=m.calls.filter(c=>c.init.method==="POST");
  assert.equal(posts.length,1);
  assert.deepEqual(JSON.parse(posts[0].init.body),{ref:"main",inputs:{probe:false}});
});
test("completed or first-run-skipped videos do not start a runner",async()=>{
  for(const entry of [{youtube:"url",instagram:"url"},{_skipped_on_first_run:true}]){
    const m=mock({__initialized__:{done:true},"__initialized__:two":{done:true},[id]:entry},
      {one:"/video/"+id,two:"/video/"+id});
    assert.equal(await dispatch(env,m.fetcher),"idle");
    assert.equal(m.calls.filter(c=>c.init.method==="POST").length,0);
  }
});
test("partial publication retries and blocked sources do not hide new uploads",async()=>{
  const m=mock({__initialized__:{done:true},[id]:{youtube:"url"}},
    {one:"/video/"+id,two:"blocked"});
  assert.equal(await dispatch(env,m.fetcher),"dispatched");
});
test("active runs and recent failures do not create more runs",async()=>{
  for(const [run,expected] of [
    [{status:"queued"},"active"],
    [{status:"completed",conclusion:"failure",updated_at:new Date().toISOString()},"retry-cooldown"],
  ]){
    const m=mock({}, {}, [run]);
    assert.equal(await dispatch(env,m.fetcher),expected);
    assert.equal(m.calls.length,1);
  }
});
test("empty discovery, bad config and dispatch errors are visible",async()=>{
  await assert.rejects(dispatch({}),/Missing/);
  assert.throws(()=>accounts({TIKTOK_USERNAMES:"https://example.com"}),/valid/);
  const m=mock({}, {});
  await assert.rejects(dispatch(env,m.fetcher),/discovery failed/);
  const bad=mock({}, {one:"/video/"+id,two:"/video/"+id},undefined,403);
  await assert.rejects(dispatch(env,bad.fetcher),/403/);
});
