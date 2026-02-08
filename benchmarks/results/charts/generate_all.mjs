import sharp from 'sharp';
const OUT = '/data/workspace/lap-poc/benchmarks/results/charts';
const BG = '#0d1117', TEXT = '#e6edf3', MUTED = '#7d8590', ACCENT = '#58a6ff', GREEN = '#3fb950', RED = '#f85149', PURPLE = '#bc8cff', YELLOW = '#d29922';

// === DATA ===
const specs = [
  ['snyk',201205,4281,47.0],['notion',68587,1609,42.6],['digitalocean',345401,12534,27.6],
  ['plaid',304530,18859,16.1],['box',232848,16228,14.3],['asana',97427,7450,13.1],
  ['hetzner',167308,13628,12.3],['slack2',126517,10484,12.1],['vercel',136159,13710,9.9],
  ['linode',203653,20740,9.8],['launchdarkly',31522,4502,7.0],['netlify',20142,2916,6.9],
  ['twitter',61043,9387,6.5],['resend',21890,3551,6.2],['gitlab',88242,14774,6.0],
  ['vonage',1889,384,4.9],['circleci',5725,1377,4.2],['petstore',4656,1122,4.1],
  ['stripe-charges',1892,462,4.1],['github-core',2190,548,4.0],['openai-core',1730,456,3.8],
  ['google-maps',941,257,3.7],['discord',909,253,3.6],['twilio-core',2465,697,3.5],
  ['slack',762,238,3.2],['sendgrid',518,163,3.2],['cloudflare',763,237,3.2],['spotify',826,262,3.2]
];

const implTests = [
  ['Stripe',3166,1736,45],['GitHub',3384,1743,49],['Twilio',3623,1857,49],
  ['Slack',2163,1639,24],['Hetzner',168388,15045,91]
];

const formats = [['OpenAPI','13.2x',13.2],['Postman','4.4x',4.4],['AsyncAPI','1.8x',1.8],['Protobuf','0.9x',0.9],['GraphQL','0.4x',0.4]];

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

// === CHART 1: Compression bar chart ===
async function chart1(){
  const W=900, barH=22, gap=4, top=60, left=130, right=80;
  const H=top+specs.length*(barH+gap)+30;
  const maxR=specs[0][3];
  const barW=W-left-right;
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="35" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">DocLean Compression Ratio by API (OpenAPI Specs)</text>`;
  specs.forEach(([name,,,ratio],i)=>{
    const y=top+i*(barH+gap);
    const w=Math.max(2,(ratio/maxR)*barW);
    const color=ratio>=10?GREEN:ratio>=5?ACCENT:PURPLE;
    svg+=`<text x="${left-8}" y="${y+barH-6}" fill="${MUTED}" font-size="11" text-anchor="end" font-family="sans-serif">${esc(name)}</text>`;
    svg+=`<rect x="${left}" y="${y}" width="${w}" height="${barH}" fill="${color}" rx="3" opacity="0.85"/>`;
    svg+=`<text x="${left+w+6}" y="${y+barH-6}" fill="${TEXT}" font-size="11" font-family="sans-serif" font-weight="600">${ratio}x</text>`;
  });
  svg+=`</svg>`;
  await sharp(Buffer.from(svg)).png().toFile(`${OUT}/compression_bar_chart.png`);
  console.log('✓ compression_bar_chart.png');
}

// === CHART 2: Token savings (top 10) ===
async function chart2(){
  const top10=specs.slice().sort((a,b)=>b[1]-a[1]).slice(0,10);
  const W=900,H=500,top=70,bottom=80,left=60,right=30;
  const maxVal=Math.max(...top10.map(s=>s[1]));
  const chartW=W-left-right, chartH=H-top-bottom;
  const groupW=chartW/top10.length, barW=groupW*0.35;
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="35" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">Token Reduction: Raw OpenAPI vs DocLean Lean</text>
<text x="${W/2}" y="55" fill="${MUTED}" font-size="11" text-anchor="middle" font-family="sans-serif">Top 10 largest specs by raw token count</text>`;
  // Y axis gridlines
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
  // Legend
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
  const W=700,H=380,top=70,bottom=50,left=80,right=40;
  const maxVal=14;
  const chartW=W-left-right, chartH=H-top-bottom;
  const barW=chartW/formats.length*0.6;
  const gap=chartW/formats.length;
  const colors=[GREEN,ACCENT,PURPLE,YELLOW,RED];
  let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
<rect width="${W}" height="${H}" fill="${BG}" rx="8"/>
<text x="${W/2}" y="35" fill="${TEXT}" font-size="16" text-anchor="middle" font-family="sans-serif" font-weight="700">Compression by Input Format</text>
<text x="${W/2}" y="55" fill="${MUTED}" font-size="11" text-anchor="middle" font-family="sans-serif">Average compression ratio (higher = more savings)</text>`;
  for(let i=0;i<=4;i++){
    const y=top+chartH*(1-i/4);
    const val=(maxVal*i/4).toFixed(0)+'x';
    svg+=`<line x1="${left}" y1="${y}" x2="${W-right}" y2="${y}" stroke="${MUTED}33" stroke-width="1"/>`;
    svg+=`<text x="${left-8}" y="${y+4}" fill="${MUTED}" font-size="9" text-anchor="end" font-family="sans-serif">${val}</text>`;
  }
  // 1x reference line
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

await chart1();
await chart2();
await chart3();
await chart4();
console.log('All charts done!');
