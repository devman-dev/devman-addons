/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AgentHierarchyWidget extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            agents: [],
            players: [],
            loading: true,
            selectedAgent: null,
            expandedAgents: new Map(), // Map para manejar múltiples niveles: agentId -> Set de sub-agentes expandidos
            hierarchyData: {},
            statistics: {
                totalAgents: 0,
                totalPlayers: 0,
                maxDepth: 0,
                rootAgents: 0
            }
        });

        onWillStart(async () => {
            await this.loadAgents();
        });
    }

    async loadAgents() {
        try {
            this.state.loading = true;

            // Cargar agentes
            const agents = await this.orm.searchRead(
                "res.partner",
                [["is_agent", "=", true]],
                ["name", "email", "phone", "parent_agent_id", "child_agent_ids", "agent_depth", "managed_player_ids", "is_player"]
            );

            // Cargar jugadores para información completa
            const players = await this.orm.searchRead(
                "res.partner",
                [["is_player", "=", true]],
                ["name", "email", "phone", "agent_id"]
            );

            this.state.agents = agents || [];
            this.state.players = players || [];
            this.processHierarchyData(agents || [], players || []);
            this.calculateStatistics(agents || [], players || []);

        } catch (error) {
            console.error("Error loading agents:", error);
            this.notification.add("Error cargando datos del organigrama", { type: "danger" });
            this.state.agents = [];
            this.state.players = [];
        } finally {
            this.state.loading = false;
        }
    }

    processHierarchyData(agents, players) {
        const hierarchy = {};

        // Procesar agentes
        agents.forEach(agent => {
            hierarchy[agent.id] = {
                ...agent,
                children: [],
                players: [],
                type: 'agent'
            };
        });

        // Establecer relaciones padre-hijo para agentes
        agents.forEach(agent => {
            if (agent.parent_agent_id && agent.parent_agent_id[0]) {
                const parentId = agent.parent_agent_id[0];
                if (hierarchy[parentId]) {
                    hierarchy[parentId].children.push(hierarchy[agent.id]);
                }
            }
        });

        // Agregar jugadores a sus agentes
        players.forEach(player => {
            if (player.agent_id && player.agent_id[0]) {
                const agentId = player.agent_id[0];
                if (hierarchy[agentId]) {
                    hierarchy[agentId].players.push({
                        ...player,
                        type: 'player'
                    });
                }
            }
        });

        this.state.hierarchyData = hierarchy;
    }

    calculateStatistics(agents, players) {
        const safeAgents = agents || [];
        const safePlayers = players || [];

        this.state.statistics = {
            totalAgents: safeAgents.length,
            totalPlayers: safePlayers.length,
            maxDepth: safeAgents.length > 0 ? Math.max(...safeAgents.map(a => a.agent_depth || 0)) : 0,
            rootAgents: safeAgents.filter(a => !a.parent_agent_id).length
        };
    }

    get rootAgents() {
        return (this.state.agents || []).filter(agent => !agent.parent_agent_id);
    }

    getSubAgents(parentId) {
        return (this.state.agents || []).filter(agent =>
            agent.parent_agent_id && agent.parent_agent_id[0] === parentId
        );
    }

    getAgentPlayers(agentId) {
        const agent = this.state.hierarchyData[agentId];
        return agent ? agent.players : [];
    }

    async onRefresh() {
        this.notification.add("Actualizando organigrama...", { type: "info" });
        await this.loadAgents();
        this.notification.add("Organigrama actualizado correctamente", { type: "success" });
    }

    onOpenAgent(agentId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: agentId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    onCreateAgent() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            views: [[false, 'form']],
            context: { 'default_is_agent': true },
            target: 'current',
        });
    }

    onCreateSubAgent(parentId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            views: [[false, 'form']],
            context: {
                'default_is_agent': true,
                'default_parent_agent_id': parentId
            },
            target: 'current',
        });
    }

    onCreatePlayer(agentId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            views: [[false, 'form']],
            context: {
                'default_is_player': true,
                'default_agent_id': agentId
            },
            target: 'current',
        });
    }

    onViewAgentManagement() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            name: 'Gestión de Agentes',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['is_agent', '=', true]],
            context: { 'default_is_agent': true },
            target: 'current',
        });
    }

    onViewPlayerManagement() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            name: 'Gestión de Jugadores',
            view_mode: 'list,form',
            domain: [['is_player', '=', true]],
            context: { 'default_is_player': true },
            target: 'current',
        });
    }

    getAgentBadgeClass(depth) {
        const classes = ['badge-primary', 'badge-info', 'badge-success', 'badge-warning', 'badge-secondary'];
        return classes[depth % classes.length];
    }

    formatAgentStats(agent) {
        const subAgents = this.getSubAgents(agent.id).length;
        const players = agent.managed_player_ids ? agent.managed_player_ids.length : 0;

        if (subAgents && players) {
            return `${subAgents} subagente(s), ${players} jugador(es)`;
        } else if (subAgents) {
            return `${subAgents} subagente(s)`;
        } else if (players) {
            return `${players} jugador(es)`;
        }
        return 'Sin asignaciones';
    }

    // Método para obtener un jugador por ID desde todos los agentes
    getPlayerById(playerId) {
        return (this.state.players || []).find(player => player.id === playerId);
    }

    // Métodos de expansión recursiva para cualquier agente en cualquier nivel
    onToggleAgent(agentId) {
        if (this.state.selectedAgent === agentId) {
            // Si ya está seleccionado, deseleccionar y limpiar todas las expansiones
            this.state.selectedAgent = null;
            this.state.expandedAgents.clear();
        } else {
            // Seleccionar nuevo agente y limpiar expansiones previas
            this.state.selectedAgent = agentId;
            this.state.expandedAgents.clear();
        }
    }

    isAgentExpanded(agentId) {
        return this.state.selectedAgent === agentId;
    }

    // Método unificado para expandir/colapsar cualquier agente en cualquier nivel
    onToggleSubAgent(agentId, event) {
        if (event) {
            event.stopPropagation();
        }

        if (this.state.expandedAgents.has(agentId)) {
            // Si está expandido, colapsarlo y todos sus descendientes
            this.collapseAgentAndDescendants(agentId);
        } else {
            // Si no está expandido, expandirlo
            this.state.expandedAgents.set(agentId, true);
        }
    }

    // Colapsar un agente y todos sus descendientes recursivamente
    collapseAgentAndDescendants(agentId) {
        this.state.expandedAgents.delete(agentId);

        // Encontrar todos los sub-agentes de este agente
        const subAgents = this.getSubAgents(agentId);
        subAgents.forEach(subAgent => {
            this.collapseAgentAndDescendants(subAgent.id);
        });
    }

    isSubAgentExpanded(agentId) {
        return this.state.expandedAgents.has(agentId);
    }

    // Método para obtener la jerarquía completa de un agente (recursivo)
    getCompleteHierarchy(agentId, level = 0) {
        const subAgents = this.getSubAgents(agentId);
        const agent = this.state.agents.find(a => a.id === agentId);
        const directPlayers = this.state.players.filter(p =>
            agent && agent.managed_player_ids && agent.managed_player_ids.includes(p.id)
        );

        return {
            agentId: agentId,
            level: level,
            subAgents: subAgents.map(subAgent => ({
                ...subAgent,
                level: level + 1,
                hierarchy: this.isSubAgentExpanded(subAgent.id) ?
                    this.getCompleteHierarchy(subAgent.id, level + 1) : null
            })),
            players: directPlayers,
            hasSubordinates: subAgents.length > 0 || directPlayers.length > 0
        };
    }

    getAgentSubHierarchy(agentId) {
        const subAgents = this.getSubAgents(agentId);
        const agent = this.state.agents.find(a => a.id === agentId);
        const players = this.state.players.filter(p =>
            agent && agent.managed_player_ids && agent.managed_player_ids.includes(p.id)
        );

        return { subAgents, players };
    }

    getSubAgentHierarchy(subAgentId) {
        const subSubAgents = this.getSubAgents(subAgentId);
        const subAgent = this.state.agents.find(a => a.id === subAgentId);
        const players = this.state.players.filter(p =>
            subAgent && subAgent.managed_player_ids && subAgent.managed_player_ids.includes(p.id)
        );

        return { subAgents: subSubAgents, players };
    }

    // Método auxiliar para verificar si un agente tiene subordinados
    hasSubordinates(agentId) {
        const subAgents = this.getSubAgents(agentId);
        const agent = this.state.agents.find(a => a.id === agentId);
        const players = agent && agent.managed_player_ids ? agent.managed_player_ids.length : 0;

        return subAgents.length > 0 || players > 0;
    }

    // Método para obtener el nombre del agente padre
    getParentAgentName(agentId) {
        const agent = this.state.agents.find(a => a.id === agentId);
        if (agent && agent.parent_agent_id) {
            const parentAgent = this.state.agents.find(a => a.id === agent.parent_agent_id[0]);
            return parentAgent ? parentAgent.name : 'Agente Principal';
        }
        return 'Agente Principal';
    }

    // Acciones para jugadores
    async onViewPlayer(playerId) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: playerId,
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'current',
        });
    }

    async onEditPlayer(playerId) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: playerId,
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
        });
    }
}

AgentHierarchyWidget.template = "casino_agentes.HierarchyView";

// Registro como acción cliente
registry.category("actions").add("agent_hierarchy_widget", AgentHierarchyWidget);
