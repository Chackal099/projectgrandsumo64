/* SYNTHETIC UNIT HARNESS. No emulator, commercial ROM or real trace is used.
 * Host prepends SHA256 and a synthetic configuration, then inserts adapter source
 * at the delimiter. Both Node and the upstream Duktape execute this same harness.
 */
var assertions=0;
function assert(value, message) { assertions++; if(!value) throw new Error(message); }
var ram=new Uint8Array(0x400000), rom=new Uint8Array(0x50000), files={}, callbacks={};
var cpu={pc:0,gpr:{sp:0x800ff000,ra:0x80001000,v0:0,a0:0,a1:0,a2:0}};
for(var i=0;i<rom.length;i++) rom[i]=(i*17+(i>>>8)*29+13)&255;
function bytesAt(address,length) {
    var p=address&0x1fffffff, source=p>=0x10000000?rom:ram;
    if(p>=0x10000000) p-=0x10000000;
    var out=new Uint8Array(length);
    for(var j=0;j<length;j++) out[j]=source[p+j];
    return out;
}
function wordAt(p) { return ((ram[p]<<24)|(ram[p+1]<<16)|(ram[p+2]<<8)|ram[p+3])>>>0; }
function putWord(p,value) { for(var b=0;b<4;b++) ram[p+b]=(value>>>((3-b)*8))&255; }
var registers={};
var mem={ramSize:ram.length,romSize:rom.length,
    getblock:function(address,length) {
        assert(address%16===0 && length>=16 && length%16===0,'unsafe upstream getblock call');
        return bytesAt(address,length);
    },
    u8:new Proxy({}, {get:function(t,k) { return bytesAt(Number(k),1)[0]; }}),
    u32:new Proxy({}, {get:function(t,k) {
        var p=Number(k)&0x1fffffff;
        return p<ram.length?wordAt(p):(registers[p]||0);
    }})};
var fs={exists:function(p) { return Object.prototype.hasOwnProperty.call(files,p); },
    open:function(p,mode) { if(mode==='wb') files[p]=''; return p; },close:function() {},
    write:function(p,data) { files[p]+=data; return data.length; },
    readfile:function(p) { return {toString:function() { return files[p]; }}; }};
var events={};
function register(name) { events[name]=function() {
    if(!callbacks[name]) callbacks[name]=[];
    callbacks[name].push(Array.prototype.slice.call(arguments));
    return callbacks[name].length;
}; }
['onexec','onpidma','onopcode','onsptask','onwrite','onpifread','onstatechange'].forEach(register);
function AddressRange(start,end) { this.start=start;this.end=end; }
var PJ64_JSAPI_VERSION='jsapi-2', EMU_RESETTING=2, EMU_RESET=3, EMU_LOADED_ROM=6, EMU_LOADED_STATE=7;
var script={timeout:function() {},keepalive:function() {}}, console={log:function() {}};
var OZTRACE={run_id:'SYNTHETIC_ADAPTER_TEST',events:'events',control:'control',
    rom_sha256:ozSha256(rom),rom_size:rom.length,rdram_bytes:ram.length,adapter_revision:'unit-test',
    emulator_revision:'MOCK_NOT_AN_EMULATOR',watch_writes:true,max_events:200000};
// INSERT_ADAPTER_HERE
function step(pc) { cpu.pc=pc; callbacks.onexec[0][1]({pc:pc}); }
function records() {
    var lines=files.events.trim().split('\n'), result=[];
    for(var k=0;k<lines.length;k++) result.push(JSON.parse(lines[k]));
    return result;
}
function ofType(kind) { return records().filter(function(e) { return e.event===kind; }); }
function pi(source,dest,count) {
    registers[0x4600000]=dest&0xffffff; registers[0x4600004]=0x10000000+source;
    registers[0x460000c]=count-1;
    callbacks.onpidma[0][0]({direction:0,dramAddress:dest,cartAddress:0xb0000000+source,length:count});
    assert(ofType('dma_visible').length===0,'PI submit must not claim visibility');
    for(var j=0;j<count;j++) ram[(dest&0x1fffffff)+j]=rom[source+j];
}
assert(ofType('capture_start')[0].rom_sha256===ozSha256(rom),'ROM identity');
for(var r=0;r<0x4af50-0x1000;r++) ram[0x80400+r]=rom[0x1000+r];
step(0x80080400);
assert(ofType('resident_visible')[0].ram_sha256===ofType('resident_visible')[0].rom_sha256,'resident snapshot');
cpu.gpr.a0=0x200;cpu.gpr.a1=0x8012c860;cpu.gpr.a2=32;
step(0x80098640);
pi(0x200,0x8012c860,32);
step(0x8012c860);
var visible=ofType('dma_visible')[0];
assert(visible.byte_count===32,'API already adds 1 to PI register length');
assert(visible.ram_sha256===visible.rom_sha256,'post-copy hash');
var exec=ofType('exec').filter(function(e) { return e.pc==='0x8012c860'; })[0];
assert(exec.image_id===visible.transfer_id,'active execution generation');
// A delay slot can still be in the callee; only caller RA+SP confirms the return.
step(0x800986e8); step(0x800986ec);
assert(ofType('wrapper_return').length===0,'no premature return before delay slot');
step(cpu.gpr.ra);
assert(ofType('wrapper_return').length===1,'caller return');
// CPU store attempt invalidates provenance even if a conditional store may fail.
putWord(0x10000,0xac000000); // sw r0,0(r0), synthetic opcode only
callbacks.onwrite[0][1]({pc:0x80010000,address:0x8012c860,value:0});
ram[0x12c860]=0;
step(0x8012c860);
var ex=ofType('exec').filter(function(e) { return e.pc==='0x8012c860'; });
assert(ex.length===2 && ex[1].image_id===null,'modified bytes must lose ROM identity');
// Indirect target is captured before its delay slot changes the source register.
putWord(0x10010,0x0320f809); // jalr t9
cpu.gpr[25]=0x8012c868;
callbacks.onopcode[0][3]({pc:0x80010010});
step(0x80010014);cpu.gpr[25]=0x80099900;step(0x8012c868);
assert(ofType('indirect')[0].target==='0x8012c868','target sampled before delay slot');
assert(ofType('indirect_outcome')[0].target_observed,'actual target dispatch separately observed');
callbacks.onsptask[0][0]({taskType:1,taskFlags:0,ucodeAddress:0x8012c868,ucodeSize:16,
    ucodeDataAddress:0x8012c878,ucodeDataSize:8,ucodeBootAddress:0x80080400,ucodeBootSize:16});
assert(ofType('rsp_task')[0].ucode_sha256.length===64,'microcode SHA256');
files.control=JSON.stringify({id:'marker1',event:'marker',name:'menu japonês',note:'synthetic'});
for(var m=0;m<4096;m++) step(0x80001000);
assert(ofType('marker')[0].name==='menu japonês','UTF8 marker round trip');
callbacks.onstatechange[0][0]({state:EMU_RESETTING});
step(0x8012c868);
var last=ofType('exec').slice(-1)[0];
assert(last.image_id===null,'reset must retire all prior load generations');
files.control=JSON.stringify({id:'stop1',event:'stop'});
for(m=0;m<4096;m++) step(0x80001000);
assert(ofType('capture_stop')[0].reason==='operator','operator closure');
var n=records().length;
step(0x8012c868);
assert(records().length===n,'no observations after stop');
// Expose only a small test result. Mock events never become capture artifacts.
var HARNESS_RESULT=JSON.stringify({source_kind:'synthetic_test',assertions:assertions,
    status:'passed',real_emulator_executed:false});
