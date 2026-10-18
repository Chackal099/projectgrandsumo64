/* Project64 24376e8 scripting adapter. Generated config and SHA-256 precede this file.
 * Hooks observe CPU dispatch/store attempts, not architectural retirement.
 * Only addresses, sizes, register context and hashes leave emulator memory.
 */
(function () {
    var cfg = OZTRACE, seq = 0, steps = 0, polls = 0, viAcks = 0;
    var stopped = false, context = 'unmarked', pending = [], wrappers = [], images = [];
    var seen = {}, seenBranches = {}, branch = null, romHashes = {}, lastCommand = null, fd;
    var residentPending = true;
    function hex(n) { return '0x'+('00000000'+(n>>>0).toString(16)).slice(-8); }
    function physical(n) {
        n=n>>>0;
        if (n>=0x80000000 && n<0xc0000000) return n&0x1fffffff;
        return null; // No guessed TLB translation.
    }
    function readBytes(address, count) {
        // Upstream getblock has unsigned prefix/middle arithmetic. Supply only
        // aligned, >=16-byte blocks; tiny reads use the byte accessor instead.
        var out = new Uint8Array(count), base=address-(address%16), length=Math.ceil((address-base+count)/16)*16;
        if (count>=16) {
            var block=mem.getblock(base,length), offset=address-base;
            for(var i=0;i<count;i++) out[i]=block[offset+i];
        } else for(var j=0;j<count;j++) out[j]=mem.u8[(address+j)>>>0];
        return out;
    }
    function digest(address, count) { return ozSha256(readBytes(address,count)); }
    function emit(type, fields) {
        var e={schema_version:2,run_id:cfg.run_id,sequence:++seq,event:type,
            host_time_ns:null,host_wall_ms:Date.now(),cpu_step:steps,vi_count:null,
            vi_ack_count:viAcks,pif_read_count:polls,thread_id:null,context:context};
        for(var key in fields) if(Object.prototype.hasOwnProperty.call(fields,key)) e[key]=fields[key];
        var line=JSON.stringify(e).replace(/[\u007f-\uffff]/g,function(c) {
            return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);
        })+'\n';
        if(fs.write(fd,line)!==line.length) throw new Error('Short trace write');
        if(seq%128===0 || type==='marker' || type==='capture_stop') {
            fs.close(fd); fd=fs.open(cfg.events,'ab');
        }
    }
    function finish(reason) {
        if(stopped) return;
        emit('capture_stop',{reason:reason,pending_pi:pending.length,pending_wrappers:wrappers.length});
        fs.close(fd); stopped=true;
        console.log('OZTRACE stopped: '+reason);
    }
    function guarded(callback) {
        return function(e) {
            if(stopped) return;
            try { callback(e); }
            catch(error) {
                // Project64 otherwise logs callback errors and keeps invoking hooks.
                try { finish('adapter_error'); }
                finally { stopped=true; }
                throw error;
            }
        };
    }
    function invalidate(start, size) {
        var end=start+size;
        for(var i=0;i<images.length;i++) {
            var next=[], spans=images[i].live;
            for(var j=0;j<spans.length;j++) {
                var lo=spans[j][0], hi=spans[j][1];
                if(start>=hi || end<=lo) next.push([lo,hi]);
                else { if(lo<start) next.push([lo,start]); if(end<hi) next.push([end,hi]); }
            }
            images[i].live=next;
        }
    }
    function imageAt(p, count) {
        if(p===null) return null;
        for(var i=images.length-1;i>=0;i--)
            for(var j=0;j<images[i].live.length;j++) {
                var span=images[i].live[j];
                if(p>=span[0] && p+count<=span[1]) return images[i];
            }
        return null;
    }
    function materialize() {
        var list=pending; pending=[];
        for(var i=0;i<list.length;i++) {
            var t=list[i], fields={transfer_id:t.id,rom_start:hex(t.rom),dest_vram:hex(t.dest),
                byte_count:t.size,completion_source:'next_cpu_step_after_pi_callback',
                hardware_completion:false,ram_sha256:digest(t.dest,t.size),rom_sha256:null};
            var key=t.rom+':'+t.size;
            if(!romHashes[key]) romHashes[key]=digest(0xb0000000+t.rom,t.size);
            fields.rom_sha256=romHashes[key];
            emit('dma_visible',fields);
            if(fields.ram_sha256===fields.rom_sha256) images.push({id:t.id,start:t.phys,
                rom:t.rom,live:[[t.phys,t.phys+t.size]]});
        }
    }
    function pollCommand() {
        if(!fs.exists(cfg.control)) return;
        var command=JSON.parse(fs.readfile(cfg.control).toString());
        if(command.id===lastCommand) return;
        lastCommand=command.id;
        if(command.event==='marker') {
            context=command.name;
            seen={}; seenBranches={}; // First observation per identity and scenario.
            emit('marker',{name:context,command_id:command.id,note:command.note||null});
            console.log('OZTRACE marker applied: '+context);
        } else if(command.event==='stop') finish('operator');
        else throw new Error('Unknown control command');
    }
    function onExec(e) {
        if(stopped) return;
        steps++;
        materialize(); // PI copies synchronously before the next CPU instruction in this pinned source.
        if(steps%4096===1) pollCommand();
        if(stopped) return;
        if(seq>=cfg.max_events) { finish('event_limit'); return; }
        var pc=e.pc>>>0, p=physical(pc);
        if(branch && steps>=branch.step+2) {
            emit('indirect_outcome',{branch_id:branch.id,pc:hex(pc),target_observed:pc===branch.target});
            branch=null;
        }
        for(var w=wrappers.length-1;w>=0;w--) {
            var call=wrappers[w];
            if(pc===call.ra && (cpu.gpr.sp>>>0)===call.sp) {
                emit('wrapper_return',{call_id:call.id,pc:hex(pc),caller_sp:hex(call.sp),v0:hex(cpu.gpr.v0)});
                wrappers.splice(w,1);
            }
        }
        if(p===0x98640) { // Actual VA is 0x80098640; the physical offset is 0x98640.
            var id='wrapper-'+(seq+1);
            wrappers.push({id:id,ra:cpu.gpr.ra>>>0,sp:cpu.gpr.sp>>>0});
            emit('wrapper_submit',{call_id:id,pc:hex(pc),caller_ra:hex(cpu.gpr.ra),caller_sp:hex(cpu.gpr.sp),
                rom_start:hex(cpu.gpr.a0),dest_vram:hex(cpu.gpr.a1),byte_count:cpu.gpr.a2>>>0});
        }
        if((p===0xa4f70 || p===0xa2bc0) && wrappers.length) {
            emit('sdk_call',{pc:hex(pc),symbol_candidate:p===0xa4f70?'osPiStartDma':'osRecvMesg',
                a0:hex(cpu.gpr.a0),a1:hex(cpu.gpr.a1),a2:hex(cpu.gpr.a2),a3:hex(cpu.gpr.a3),
                caller_ra:hex(cpu.gpr.ra),caller_sp:hex(cpu.gpr.sp)});
        }
        if(p===0x80400 && residentPending) {
            residentPending=false;
            var residentId='resident-'+(seq+1), residentSize=0x4af50-0x1000;
            var ramHash=digest(0x80080400,residentSize), sourceHash=digest(0xb0001000,residentSize);
            emit('resident_visible',{transfer_id:residentId,rom_start:hex(0x1000),dest_vram:hex(0x80080400),
                byte_count:residentSize,ram_sha256:ramHash,rom_sha256:sourceHash,
                completion_source:'entrypoint_memory_snapshot',hardware_completion:false});
            if(ramHash===sourceHash) images.push({id:residentId,start:0x80400,rom:0x1000,
                live:[[0x80400,0x80400+residentSize]]});
        }
        if(p===0x80400 || p===0x93400) emit('boot_checkpoint',{pc:hex(pc)});
        if(p===null || p>=cfg.rdram_bytes) {
            var unknownKey='unmapped:'+pc;
            if(!seen[unknownKey]) { seen[unknownKey]=true; emit('exec',{pc:hex(pc),image_id:null}); }
            return;
        }
        var image=imageAt(p,4), key=(image?image.id:'unknown')+':'+p;
        if(!seen[key]) {
            seen[key]=true;
            emit('exec',{pc:hex(pc),image_id:image?image.id:null});
        }
    }
    function onPi(e) {
        if(stopped) return;
        var cart=e.cartAddress>>>0, physCart=physical(cart), dest=e.dramAddress>>>0, p=physical(dest);
        var id='pi-'+(seq+1), size=e.length>>>0;
        emit('dma_submit',{transfer_id:id,layer:'PI',direction:e.direction===0?'cart_to_ram':'ram_to_cart',
            pc:hex(cpu.pc),caller_ra:hex(cpu.gpr.ra),cart_address:hex(cart),dest_vram:hex(dest),byte_count:size,
            dram_register:hex(mem.u32[0xa4600000]),cart_register:hex(mem.u32[0xa4600004]),
            length_register:hex(mem.u32[e.direction===0?0xa460000c:0xa4600008])});
        if(e.direction!==0 || p===null || p+size>cfg.rdram_bytes) return;
        // Invalidate even when the source is a save device or otherwise unknown.
        // Guard bytes cover PI alignment edge effects; requested interval must hash-match.
        var lo=p-(p%8), hi=Math.min(cfg.rdram_bytes,Math.ceil((p+size)/8)*8+8);
        invalidate(lo,hi-lo);
        emit('overwrite',{cause:'PI_submit_conservative',start_physical:hex(lo),byte_count:hi-lo,transfer_id:id});
        if(physCart===null || physCart<0x10000000 || physCart+size>0x10000000+cfg.rom_size) return;
        pending.push({id:id,rom:physCart-0x10000000,dest:dest,phys:p,size:size});
    }
    function onIndirect(e) {
        if(stopped) return;
        var word=mem.u32[e.pc], rs=(word>>>21)&31, fun=word&63;
        if(fun===8 && rs===31) return;
        var target=cpu.gpr[rs]>>>0, from=imageAt(physical(e.pc),4), to=imageAt(physical(target),4);
        var key=(from?from.id:'unknown')+':'+e.pc+':'+(to?to.id:'unknown')+':'+target;
        if(seenBranches[key]) return;
        seenBranches[key]=true;
        var id='branch-'+(seq+1);
        branch={id:id,target:target,step:steps};
        emit('indirect',{branch_id:id,pc:hex(e.pc),target:hex(target),register:rs,kind:fun===9?'jalr':'jr',
            target_observed:false,delay_slot_pending:true});
    }
    function taskFields(e) {
        var fields={task_ptr:null,task_type:e.taskType,task_flags:e.taskFlags,
            ucode_vram:hex(e.ucodeAddress),ucode_size:e.ucodeSize,
            ucode_data_vram:hex(e.ucodeDataAddress),ucode_data_size:e.ucodeDataSize,
            ucode_boot_vram:hex(e.ucodeBootAddress),ucode_boot_size:e.ucodeBootSize,
            ucode_sha256:null,ucode_data_sha256:null};
        var p=physical(e.ucodeAddress), d=physical(e.ucodeDataAddress);
        if(e.ucodeSize>0 && e.ucodeSize<=0x10000 && p!==null && p+e.ucodeSize<=cfg.rdram_bytes)
            fields.ucode_sha256=digest(e.ucodeAddress,e.ucodeSize);
        if(e.ucodeDataSize>0 && e.ucodeDataSize<=0x10000 && d!==null && d+e.ucodeDataSize<=cfg.rdram_bytes)
            fields.ucode_data_sha256=digest(e.ucodeDataAddress,e.ucodeDataSize);
        return fields;
    }
    function onTask(e) { if(!stopped) emit('rsp_task',taskFields(e)); }
    function onWrite(e) {
        if(stopped) return;
        var p=physical(e.address), word=mem.u32[e.pc], op=word>>>26;
        var widths={40:1,41:2,42:4,43:4,44:8,45:8,46:4,56:4,57:4,60:8,61:8,63:8};
        var width=widths[op]||8, start=p, ambiguous=(op===42||op===44||op===45||op===46||op===56||op===60);
        if(ambiguous) start=p-(p%width);
        var touches=false;
        for(var i=0;i<width;i++) if(imageAt(start+i,1)) { touches=true; break; }
        var bss=start>=0xca350 && start<0x125130;
        if(touches || bss) {
            invalidate(start,width);
            emit('write_attempt',{pc:hex(e.pc),start_physical:hex(start),byte_count:width,
                zero_value:e.fpu?null:(e.value===0 && (!e.valueHi || e.valueHi===0)),bss_candidate:bss,
                conservative:ambiguous,committed:false});
        }
        if(p===0x120898) emit('callback_write',{pc:hex(e.pc),slot:hex(e.address),target:hex(e.value),committed:false});
    }
    function pifRead() {
        if(stopped) return;
        polls++;
        var siDest=mem.u32[0xa4800000]&0x1fffffff;
        if(siDest+64<=cfg.rdram_bytes) {
            invalidate(siDest,64);
            emit('overwrite',{cause:'SI_PIF_to_RAM',start_physical:hex(siDest),byte_count:64});
        }
        var offset=0, channel=0;
        while(offset<63 && channel<4) {
            var tx=mem.u8[0xbfc007c0+offset];
            if(tx===254) break;
            if(tx===255 || tx===253) { offset++; continue; }
            if(tx===0) { channel++; offset++; continue; }
            tx &=63;
            var rx=mem.u8[0xbfc007c1+offset], command=mem.u8[0xbfc007c2+offset], response=offset+2+tx;
            if(tx===1 && (rx&63)===4 && command===1 && response+4<=63) {
                emit('input_poll',{controller:channel,error_flags:rx&192,
                    buttons:(mem.u8[0xbfc007c0+response]<<8)|mem.u8[0xbfc007c1+response],
                    stick_x:(mem.u8[0xbfc007c2+response]<<24)>>24,
                    stick_y:(mem.u8[0xbfc007c3+response]<<24)>>24});
            }
            offset+=2+tx+(rx&63); channel++;
        }
    }
    function spReadLength(e) {
        if(stopped) return;
        var target=mem.u32[0xa4040000]&0x1fff, length=((e.value>>>0)&0xfff)+1;
        var source=mem.u32[0xa4040004]&0xffffff;
        if(target===0xfc0 && length>=64 && source+64<=cfg.rdram_bytes)
            emit('rsp_task_upload',{task_ptr:hex(source|0x80000000),pc:hex(e.pc),
                task_type:mem.u32[(source|0x80000000)>>>0],stage:'SP_DMA_submission',
                creation_observed:false});
    }
    // Do not reuse a trace path, even if the script is restarted after a crash.
    if(PJ64_JSAPI_VERSION!=='jsapi-2') throw new Error('Requires the verified Project64 jsapi-2 API');
    if(fs.exists(cfg.events)) throw new Error('Trace already exists; prepare a new run');
    fd=fs.open(cfg.events,'wb');
    script.timeout(120000);
    var loadedHash=digest(0xb0000000,mem.romSize);
    emit('capture_start',{rom_sha256:loadedHash,rom_size:mem.romSize,rdram_bytes:mem.ramSize,
        adapter_revision:cfg.adapter_revision,emulator_revision:cfg.emulator_revision,
        api_version:PJ64_JSAPI_VERSION,source_kind:'emulator',cpu_mode:'interpreter',watch_writes:cfg.watch_writes});
    if(loadedHash!==cfg.rom_sha256 || mem.ramSize!==cfg.rdram_bytes) {
        finish('identity_mismatch'); throw new Error('Loaded ROM or RDRAM configuration mismatch');
    }
    events.onexec(new AddressRange(0,0xffffffff),guarded(onExec));
    events.onpidma(guarded(onPi));
    events.onopcode(new AddressRange(0,0xffffffff),9,0xfc00003f,guarded(onIndirect));
    events.onopcode(new AddressRange(0,0xffffffff),8,0xfc00003f,guarded(onIndirect));
    events.onsptask(guarded(onTask));
    events.onpifread(guarded(pifRead));
    if(cfg.watch_writes) {
        events.onwrite(new AddressRange(0x80000000,0x80000000+cfg.rdram_bytes-1),guarded(onWrite));
        events.onwrite(new AddressRange(0xa0000000,0xa0000000+cfg.rdram_bytes-1),guarded(onWrite));
    }
    function viAck() { if(!stopped) viAcks++; }
    events.onwrite(0xa4400010,viAck);
    events.onwrite(0x84400010,viAck);
    events.onwrite(0xa4040008,guarded(spReadLength));
    events.onwrite(0x84040008,guarded(spReadLength));
    events.onstatechange(guarded(function(e) {
        if(stopped) return;
        var reset=e.state===EMU_RESETTING || e.state===EMU_RESET;
        if(reset) {
            pending=[]; wrappers=[]; images=[]; seen={}; seenBranches={}; branch=null; residentPending=true;
        }
        emit('emulator_state',{state:e.state,memory_reset:reset});
        if(e.state===EMU_LOADED_STATE) finish('savestate_not_supported');
        if(e.state===EMU_LOADED_ROM) finish('rom_changed');
    }));
    script.keepalive(true);
    console.log('OZTRACE armed; hard reset now; markers/stop via trace.py command');
})();
