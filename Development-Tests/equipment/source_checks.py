from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_paths import game_root, baseline_game_root, script_root, frozen_archive
import json,hashlib
root=game_root()
read=lambda p:(root/p).read_text(encoding='utf-8',errors='surrogateescape')
checks={}
drag=read('client/ui/ms/vgui_equipmentdrag.cpp')
ui=read('client/ui/ms/vgui_characterinventory.cpp')
container=read('client/ui/ms/vgui_containerlist.cpp')
checks['gesture_is_value_state']='MSREquipment::Gesture m_ItemDrag;' in read('client/ui/ms/vgui_containerlist.h')
checks['no_local_wear_or_transfer']='->WearItem(' not in drag and '->GiveTo(' not in drag and '->UseItem(' not in drag
checks['gesture_consumed_before_dispatch']=drag.index('const auto gesture=m_ItemDrag.Take()')<drag.index('SendEquipmentDrop(gesture.id')
checks['all_required_positions_checked']='MSREquipment::Compatible(Positions(),Requirements(item),EquipmentTargetAt(x,y))' in drag
checks['server_capability_announced']='pfnSetPhysicsKeyValue(edict(), "msr_equip_guard", "1")' in read('server/player/player.cpp')
checks['client_capability_checked']='if (!EquipmentDragAvailable()) return;' in drag
checks['close_cancels']='void CContainerPanel::Close(void)\n{\n\tCancelItemDrag();' in container
checks['page_cancels']='void CContainerPanel::ShowPage(int page)\n{\n    CancelItemDrag();' in ui
checks['rebuild_cancels']='void CContainerPanel::Update()\n{\n    CancelItemDrag();' in ui
checks['vidinit_cancels']='m_pContainerMenu->CancelItemDrag();' in read('client/ui/vgui_int.cpp')
checks['worn_index_fixed']='iSlots += pItemWorn->m_WearPositions[iwloc].Slots;' in read('shared/weapons/genericitem.cpp')
checks['client_reset_reaches_created_script']='if (playerScript) playerScript->RunScriptEventByName("game_reset_wear_positions");' in read('server/player/playershared.cpp')
checks['vidinit_does_not_reinitialize_player']='InitialSpawn' not in read('client/ui/vgui_int.cpp')
checks['item_factory_keeps_authored_spawn']='pItem->Spawn();' in read('shared/weapons/genericitem.cpp') and 'CallScriptEvent("game_spawn");' in read('shared/weapons/genericitem.cpp')
checks['worldmap_footer_uses_return_hint']=': "Press P or Escape to return to the game."' in ui
frozen=frozen_archive('MSR_CANDIDATE06_REVIEW')
manifest=json.loads((frozen/'bundle-manifest.json').read_text())
checks['candidate06_133_frozen_payloads_unchanged']=all(hashlib.sha256((frozen/p).read_bytes()).hexdigest()==r['sha256'] for p,r in manifest['files'].items())
frozen07=frozen_archive('MSR_CANDIDATE07_REVIEW')
manifest07=json.loads((frozen07/'bundle-manifest.json').read_text())
checks['candidate07_233_frozen_payloads_unchanged']=all(hashlib.sha256((frozen07/p).read_bytes()).hexdigest()==r['sha256'] for p,r in manifest07['files'].items())
result={'checks':checks,'runtime_performed':False}
Path(__file__).with_name('source-checks.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2));assert all(checks.values())
