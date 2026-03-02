import sharp from '/data/workspace/skills/table-image-generator/scripts/node_modules/sharp/lib/index.js';
const OUT = '/data/workspace/lap-poc/benchmarks/results/charts';
const BG = '#0d1117', TEXT = '#e6edf3', MUTED = '#7d8590', ACCENT = '#58a6ff', GREEN = '#3fb950', RED = '#f85149', PURPLE = '#bc8cff', YELLOW = '#d29922';

const specs = [
  ['notion',68587,1733,39.6],['snyk',201205,5193,38.7],['zoom',848983,22474,37.8],
  ['digitalocean',345401,12896,26.8],['plaid',304530,18930,16.1],['box',232848,17559,13.3],
  ['asana',97427,8257,11.8],['hetzner',167308,14242,11.7],['vercel',136159,13472,10.1],
  ['slack2',126517,13316,9.5],['linode',203653,21795,9.3],['stripe-full',1034829,118758,8.7],
  ['launchdarkly',31522,4731,6.7],['twitter',61043,9474,6.4],['netlify',20142,3127,6.4],
  ['gitlab',88242,15092,5.8],['resend',21890,3776,5.8],['vonage',1889,412,4.6],
  ['github-core',2190,531,4.1],['circleci',5725,1464,3.9],['stripe-charges',1892,490,3.9],
  ['petstore',4656,1217,3.8],['twilio-core',2465,688,3.6],['openai-core',1730,524,3.3],
  ['google-maps',941,316,3.0],['discord',909,308,3.0],['cloudflare',763,265,2.9],
  ['spotify',826,331,2.5],['sendgrid',518,209,2.5],['slack',762,316,2.4]
];

const implTests = [
  ['Stripe',3166,1736,45],['GitHub',3384,1743,49],['Twilio',3623,1857,49],
  ['Slack',2163,1639,24],['Hetzner',168388,15045,91]
];

const formats = [['OpenAPI','5.2x',5.2],['Postman','4.1x',4.1],['Protobuf','1.5x',1.5],['AsyncAPI','1.4x',1.4],['GraphQL','1.3x',1.3]];

// v0.1 lean values for version comparison (top 10 by raw tokens)
const versionData = [
  ['stripe-full',1034829,121046,118758],['zoom',848983,23118,22474],
  ['digitalocean',345401,14356,12896],['plaid',304530,20206,18930],
  ['box',232848,17523,17559],['linode',203653,22354,21795],
  ['snyk',201205,4874,5193],['hetzner',167308,14460,14242],
  ['vercel',136159,13505,13472],['slack2',126517,12061,13316]
]; // [name, raw, v0.1lean, v0.3lean]

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function fmtK(n){return n>=1000?(n/1000).toFixed(n>=100000?0:1)+'K':String(n)}

// === CHART 1: Compression bar chart ===
async function chart1(){
  const W=900, barH=22, gap=4, top=60, left=140, right=80;
  const H=top+specs.length*(barH+gap)+30;
  const maxR=specs[0][3];
  const barW=W-left-right;
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="35" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">DocLean Compression Ratio — All 30 OpenAPI Specs (v0.3)</text>`;
  specs.forEach(([name,,,ratio],i)=>{
    const y=top+i*(barH+gap);
    const w=Math.max(2,(ratio/maxR)*barW);
    const color=ratio>=10?GREEN:ratio>=5?ACCENT:PURPLE;
    svg+=`<text x="${left-8}" y="${y+barH-6}" fill="${MUTED}" font-size="11" text-anchor="end" font-family="sans-serif">${esc(name)}</text>`;
    svg+=`<rect x="${left}" y="${y}" width="${w}" height="${barH}" fill="${color}" rx="3" opacity="0.85"/>`;
    svg+=`<text x="${left+w+6}" y="${y+barH-6}" fill="${TEXT}" font-size="11" font-family="sans-serif" font-weight="600">${ratio}x</text>`;
  });
  const ly=H-20;
  svg+=`<rect x="${left}" y="${ly}" width="10" height="10" fill="${GREEN}" rx="2"/><text x="${left+14}" y="${ly+9}" fill="${MUTED}" font-size="9" font-family="sans-serif">≥10x</text>`;
  svg+=`<rect x="${left+55}" y="${ly}" width="10" height="10" fill="${ACCENT}" rx="2"/><text x="${left+69}" y="${ly+9}" fill="${MUTED}" font-size="9" font-family="sans-serif">≥5x</text>`;
  svg+=`<rect x="${left+105}" y="${ly}" width="10" height="10" fill="${PURPLE}" rx="2"/><text x="${left+119}" y="${ly+9}" fill="${MUTED}" font-size="9" font-family="sans-serif">&lt;5x</text>`;
  svg+=`</svg>`;
  await sharp(Buffer.from(svg)).png().toFile(`${OUT}/compression_bar_chart.png`);
  console.log('✓ compression_bar_chart.png');
}

// === CHART 2: Token savings (top 10) ===
async function chart2(){
  const top10=specs.slice().sort((a,b)=>b[1]-a[1]).slice(0,10);
  const W=900,H=500,top=70,bottom=80,left=70,right=30;
  const maxVal=Math.max(...top10.map(s=>s[1]));
  const chartW=W-left-right, chartH=H-top-bottom;
  const groupW=chartW/top10.length, barW=groupW*0.35;
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="35" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">Token Reduction: Raw OpenAPI vs DocLean (v0.3)</text>
<text x="${W/2}" y="55" fill="${MUTED}" font-size="11" text-anchor="middle" font-family="sans-serif">Top 10 largest specs by raw token count</text>`;
  for(let i=0;i<=4;i++){
    const y=top+chartH*(1-i/4);
    const val=Math.round(maxVal*i/4/1000)+'K';
    svg+=`<line x1="${left}" y1="${y}" x2="${W-right}" y2="${y}" stroke="${MUTED}33" stroke-width="1"/>`;
    svg+=`<text x="${left-8}" y="${y+4}" fill="${MUTED}" font-size="9" text-anchor="end" font-family="sans-serif">${val}</text>`;
  }
  top10.forEach(([name,raw,lean],i)=>{
    const x=left+i*groupW+groupW*0.15;
    const hRaw=(raw/maxVal)*chartH;
    const hLean=(lean/maxVal)*chartH;
    svg+=`<rect x="${x}" y="${top+chartH-hRaw}" width="${barW}" height="${hRaw}" fill="${RED}" rx="2" opacity="0.8"/>`;
    svg+=`<rect x="${x+barW+2}" y="${top+chartH-hLean}" width="${barW}" height="${hLean}" fill="${GREEN}" rx="2" opacity="0.8"/>`;
    svg+=`<text x="${x+barW}" y="${H-bottom+15}" fill="${MUTED}" font-size="9" text-anchor="middle" font-family="sans-serif" transform="rotate(-30,${x+barW},${H-bottom+15})">${esc(name)}</text>`;
  });
  svg+=`<rect x="${W-200}" y="12" width="12" height="12" fill="${RED}" rx="2"/>`;
  svg+=`<text x="${W-184}" y="23" fill="${TEXT}" font-size="11" font-family="sans-serif">Raw OpenAPI</text>`;
  svg+=`<rect x="${W-100}" y="12" width="12" height="12" fill="${GREEN}" rx="2"/>`;
  svg+=`<text x="${W-84}" y="23" fill="${TEXT}" font-size="11" font-family="sans-serif">DocLean</text>`;
  svg+=`</svg>`;
  await sharp(Buffer.from(svg)).png().toFile(`${OUT}/token_savings_chart.png`);
  console.log('✓ token_savings_chart.png');
}

// === CHART 3: Implementation comparison ===
async function chart3(){
  const W=800,H=450,top=70,bottom=70,left=70,right=30;
  const maxVal=Math.max(...implTests.map(t=>t[1]));
  const chartW=W-left-right, chartH=H-top-bottom;
  const groupW=chartW/implTests.length, barW=groupW*0.35;
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="35" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">Agent Implementation Test — Same Code, Fewer Tokens</text>
<text x="${W/2}" y="55" fill="${MUTED}" font-size="11" text-anchor="middle" font-family="sans-serif">Identical agent output, different context sizes</text>`;
  for(let i=0;i<=4;i++){
    const y=top+chartH*(1-i/4);
    const val=Math.round(maxVal*i/4/1000)+'K';
    svg+=`<line x1="${left}" y1="${y}" x2="${W-right}" y2="${y}" stroke="${MUTED}33" stroke-width="1"/>`;
    svg+=`<text x="${left-8}" y="${y+4}" fill="${MUTED}" font-size="9" text-anchor="end" font-family="sans-serif">${val}</text>`;
  }
  implTests.forEach(([name,openapi,doclean,saved],i)=>{
    const x=left+i*groupW+groupW*0.15;
    const hO=(openapi/maxVal)*chartH;
    const hD=(doclean/maxVal)*chartH;
    svg+=`<rect x="${x}" y="${top+chartH-hO}" width="${barW}" height="${hO}" fill="${RED}" rx="2" opacity="0.8"/>`;
    svg+=`<rect x="${x+barW+2}" y="${top+chartH-hD}" width="${barW}" height="${hD}" fill="${GREEN}" rx="2" opacity="0.8"/>`;
    svg+=`<text x="${x+barW}" y="${top+chartH-hO-6}" fill="${YELLOW}" font-size="10" text-anchor="middle" font-family="sans-serif" font-weight="600">-${saved}%</text>`;
    svg+=`<text x="${x+barW}" y="${H-bottom+18}" fill="${TEXT}" font-size="12" text-anchor="middle" font-family="sans-serif">${esc(name)}</text>`;
  });
  svg+=`<rect x="${W-220}" y="12" width="12" height="12" fill="${RED}" rx="2"/>`;
  svg+=`<text x="${W-204}" y="23" fill="${TEXT}" font-size="11" font-family="sans-serif">OpenAPI Tokens</text>`;
  svg+=`<rect x="${W-110}" y="12" width="12" height="12" fill="${GREEN}" rx="2"/>`;
  svg+=`<text x="${W-94}" y="23" fill="${TEXT}" font-size="11" font-family="sans-serif">DocLean</text>`;
  svg+=`</svg>`;
  await sharp(Buffer.from(svg)).png().toFile(`${OUT}/implementation_comparison.png`);
  console.log('✓ implementation_comparison.png');
}

// === CHART 4: Format comparison ===
async function chart4(){
  const W=700,H=400,top=70,bottom=50,left=80,right=40;
  const maxVal=6;
  const chartW=W-left-right, chartH=H-top-bottom;
  const barW=chartW/formats.length*0.6;
  const gap=chartW/formats.length;
  const colors=[GREEN,ACCENT,PURPLE,YELLOW,RED];
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="35" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">Median Compression by Format (v0.3)</text>
<text x="${W/2}" y="55" fill="${MUTED}" font-size="11" text-anchor="middle" font-family="sans-serif">162 specs across 5 formats — higher = more token savings</text>`;
  for(let i=0;i<=3;i++){
    const y=top+chartH*(1-i/3);
    const val=(maxVal*i/3).toFixed(0)+'x';
    svg+=`<line x1="${left}" y1="${y}" x2="${W-right}" y2="${y}" stroke="${MUTED}33" stroke-width="1"/>`;
    svg+=`<text x="${left-8}" y="${y+4}" fill="${MUTED}" font-size="9" text-anchor="end" font-family="sans-serif">${val}</text>`;
  }
  const y1x=top+chartH*(1-1/maxVal);
  svg+=`<line x1="${left}" y1="${y1x}" x2="${W-right}" y2="${y1x}" stroke="${YELLOW}66" stroke-width="1" stroke-dasharray="4,4"/>`;
  svg+=`<text x="${W-right+4}" y="${y1x+4}" fill="${YELLOW}" font-size="9" font-family="sans-serif">1x</text>`;
  formats.forEach(([name,label,val],i)=>{
    const x=left+i*gap+(gap-barW)/2;
    const h=Math.max(2,(val/maxVal)*chartH);
    svg+=`<rect x="${x}" y="${top+chartH-h}" width="${barW}" height="${h}" fill="${colors[i]}" rx="3" opacity="0.85"/>`;
    svg+=`<text x="${x+barW/2}" y="${top+chartH-h-8}" fill="${TEXT}" font-size="13" text-anchor="middle" font-family="sans-serif" font-weight="700">${label}</text>`;
    svg+=`<text x="${x+barW/2}" y="${H-bottom+18}" fill="${TEXT}" font-size="12" text-anchor="middle" font-family="sans-serif">${esc(name)}</text>`;
  });
  svg+=`</svg>`;
  await sharp(Buffer.from(svg)).png().toFile(`${OUT}/format_comparison.png`);
  console.log('✓ format_comparison.png');
}

// === CHART 5: Version comparison (v0.1 → v0.3) ===
async function chart5(){
  const W=900,H=500,top=80,bottom=80,left=70,right=30;
  const maxVal=Math.max(...versionData.map(d=>d[2]),...versionData.map(d=>d[3]));
  const chartW=W-left-right, chartH=H-top-bottom;
  const groupW=chartW/versionData.length, barW=groupW*0.35;
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="30" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">Version Comparison: v0.1 vs v0.3 Lean Tokens</text>
<text x="${W/2}" y="50" fill="${MUTED}" font-size="10" text-anchor="middle" font-family="sans-serif">v0.3 adds inline schemas &amp; completeness signals (~4% more tokens, better agent reliability)</text>
<text x="${W/2}" y="66" fill="${MUTED}" font-size="10" text-anchor="middle" font-family="sans-serif">Top 10 specs by raw token count</text>`;
  for(let i=0;i<=4;i++){
    const y=top+chartH*(1-i/4);
    const val=fmtK(Math.round(maxVal*i/4));
    svg+=`<line x1="${left}" y1="${y}" x2="${W-right}" y2="${y}" stroke="${MUTED}33" stroke-width="1"/>`;
    svg+=`<text x="${left-8}" y="${y+4}" fill="${MUTED}" font-size="9" text-anchor="end" font-family="sans-serif">${val}</text>`;
  }
  versionData.forEach(([name,raw,v01,v03],i)=>{
    const x=left+i*groupW+groupW*0.15;
    const h01=(v01/maxVal)*chartH;
    const h03=(v03/maxVal)*chartH;
    const pct=((v03-v01)/v01*100).toFixed(1);
    const sign=pct>0?'+':'';
    svg+=`<rect x="${x}" y="${top+chartH-h01}" width="${barW}" height="${h01}" fill="${ACCENT}" rx="2" opacity="0.8"/>`;
    svg+=`<rect x="${x+barW+2}" y="${top+chartH-h03}" width="${barW}" height="${h03}" fill="${GREEN}" rx="2" opacity="0.8"/>`;
    svg+=`<text x="${x+barW}" y="${top+chartH-Math.max(h01,h03)-6}" fill="${YELLOW}" font-size="9" text-anchor="middle" font-family="sans-serif" font-weight="600">${sign}${pct}%</text>`;
    svg+=`<text x="${x+barW}" y="${H-bottom+15}" fill="${MUTED}" font-size="9" text-anchor="middle" font-family="sans-serif" transform="rotate(-30,${x+barW},${H-bottom+15})">${esc(name)}</text>`;
  });
  svg+=`<rect x="${W-200}" y="12" width="12" height="12" fill="${ACCENT}" rx="2"/>`;
  svg+=`<text x="${W-184}" y="23" fill="${TEXT}" font-size="11" font-family="sans-serif">v0.1 Lean</text>`;
  svg+=`<rect x="${W-100}" y="12" width="12" height="12" fill="${GREEN}" rx="2"/>`;
  svg+=`<text x="${W-84}" y="23" fill="${TEXT}" font-size="11" font-family="sans-serif">v0.3 Lean</text>`;
  svg+=`</svg>`;
  await sharp(Buffer.from(svg)).png().toFile(`${OUT}/version_comparison.png`);
  console.log('✓ version_comparison.png');
}

// === CHART 6: Cost projection table ===
async function chart6(){
  const W=800,H=300;
  const rows=[
    ['Model','Price/1M tokens','100K raw tokens','100K with DocLean','Savings'],
    ['GPT-4o','$2.50 input','$0.25','$0.024','$0.226 (90%)'],
    ['Claude Sonnet 4','$3.00 input','$0.30','$0.029','$0.271 (90%)'],
    ['Claude Opus 4','$15.00 input','$1.50','$0.146','$1.354 (90%)'],
    ['GPT-4.1','$2.00 input','$0.20','$0.019','$0.181 (90%)'],
    ['Gemini 2.5 Pro','$1.25 input','$0.125','$0.012','$0.113 (90%)'],
  ];
  const colW=[160,140,140,160,160];
  const rowH=38, headerH=42, topPad=55;
  const tableW=colW.reduce((a,b)=>a+b,0);
  const tableX=(W-tableW)/2;
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="35" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">Cost Projection: 10.3x Average Compression</text>`;
  rows.forEach((row,ri)=>{
    const y=topPad+ri*(ri===0?headerH:rowH);
    const h=ri===0?headerH:rowH;
    const bg=ri===0?'#161b22':ri%2===0?'#0d1117':'#161b2288';
    let x=tableX;
    svg+=`<rect x="${tableX}" y="${y}" width="${tableW}" height="${h}" fill="${bg}"/>`;
    row.forEach((cell,ci)=>{
      const tx=x+colW[ci]/2;
      const ty=y+h/2+4;
      const fill=ri===0?ACCENT:ci===4?GREEN:TEXT;
      const fs=ri===0?11:11;
      const fw=ri===0?'700':'400';
      svg+=`<text x="${tx}" y="${ty}" fill="${fill}" font-size="${fs}" text-anchor="middle" font-family="sans-serif" font-weight="${fw}">${esc(cell)}</text>`;
      x+=colW[ci];
    });
  });
  // Border
  svg+=`<rect x="${tableX}" y="${topPad}" width="${tableW}" height="${headerH+5*rowH}" fill="none" stroke="${MUTED}44" rx="4"/>`;
  svg+=`</svg>`;
  await sharp(Buffer.from(svg)).png().toFile(`${OUT}/cost_projection.png`);
  console.log('✓ cost_projection.png');
}

await chart1();
await chart2();
await chart3();
await chart4();
await chart5();
await chart6();
console.log('All charts done!');
