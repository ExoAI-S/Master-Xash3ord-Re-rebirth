#pragma once

// Node child access that also works for 32-bit BSP2 ("QBSP2") maps.
//
// On 32-bit builds Xash3D FWGS packs a BSP2 node's children into the same
// eight bytes GoldSrc uses for two pointers: per child, bit 0 = leaf flag and
// bits 1..23 = signed index into model->leafs or model->nodes
// (engine common/com_model.h, node_child()). The model carries MODEL_QBSP2.

#include <cstring>

constexpr int MSR_MODEL_QBSP2 = 1 << 28;

inline mnode_t *MSR_NodeChild(const mnode_t *node, int side)
{
	cl_entity_t *world = gEngfuncs.GetEntityByIndex(0);
	model_t *mod = world ? world->model : nullptr;
	if (mod && (mod->flags & MSR_MODEL_QBSP2))
	{
		unsigned int packed[2];
		memcpy(packed, &node->children[0], sizeof(packed));
		const unsigned int bits = packed[side ? 1 : 0];
		const int index = (int)(bits << 8) >> 9; // signed 23-bit field at bits 1..23
		if (bits & 1)
			return (mnode_t *)(mod->leafs + index);
		return mod->nodes + index;
	}
	return node->children[side ? 1 : 0];
}
