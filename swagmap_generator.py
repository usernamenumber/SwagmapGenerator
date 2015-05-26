#!/usr/bin/python
import yaml, igraph
def parse_skills(skills):
    parsed = set()
    if not hasattr(skills,"__iter__"):
        skills = [skills]
    for skillstring in skills:
        tokens = [ s.lower().strip() for s in skillstring.split(":") ]
        prefix = tokens[:-1]
        for skill in tokens[-1].split(","):
            if skill is not None:
                parsed.add(":".join([ x.strip() for x in prefix + [skill] ]))
    return parsed
            
class ProjectLibrary(object):
    @staticmethod
    def from_yaml_file(fn):        
        swagifacts_yml = open(fn,"r").read()
        return ProjectLibrary.from_yaml(swagifacts_yml)
            
    @staticmethod
    def from_yaml(swagifacts_yml):
        swagifacts_yml = swagifacts_yml.lower()
        return ProjectLibrary(yaml.load(swagifacts_yml))  
        
    def __init__(self,projects={}):
        self.skills_provided_by_project = {}
        self.projects_by_skill_provided = {}
        self.skills_required_by_project = {}
        self.projects_by_skill_required = {}
        self.project_dependencies = {}
        self.projects_raw = {}
        self.graph = None
        self.add_projects(projects)
        
    def add_projects(self,projects):
        self.projects_raw.update(projects)
        self._update_indexes()
        
    def _update_indexes(self):
        (self.skills_provided_by_project,
         self.skills_required_by_project,
         self.projects_by_skill_required,
         self.projects_by_skill_provided,
         self.projects_that_extend,
         self.projects_extended_by
         ) = self._index_projects() 
            
    def as_graph(self,reset=False):
        if self.graph is None or reset:
            g = igraph.Graph(directed=True)
            g.add_vertex("root",label="START",noun="state")
            skills = set()
            for project,props in self.projects_raw.items():
                requires = parse_skills(props.get("requires",[]))
                provides = parse_skills(props.get("provides",[]))
                extends  = props.get("extends",[])
                description = props.get("description","No description")
                g.add_vertex(
                    project,
                    label=project,
                    noun="project",
                    requires=requires,
                    provides=provides,
                    extends=extends,
                    description=description
                )
                skills.update(requires)
                skills.update(provides)
            for skill in skills:
                g.add_vertex(skill,label=skill,noun="skill")
                
                
            for project,props in self.projects_raw.items():
                requires = parse_skills(props.get("requires",["root"]))
                provides = parse_skills(props.get("provides",[]))
                extends  = parse_skills(props.get("extends",[]))
                for skill in requires:
                    g.add_edge(skill,project,verb="requires")
                for skill in provides:
                    g.add_edge(project,skill,verb="provides")
                for extended_project in extends:
                    g.add_edge(extended_project, verb="extended by")
            
            g.vs["color"] = [{
                "project":"cyan",
                "skill":"lightgreen",
                "state":"green"
                }[noun] for noun in g.vs["noun"]]
            g.es["color"] = [{
                "provides":"darkgray",
                "requires":"darkgray",
                "extends":"black"
                }[verb] for verb in g.es["verb"]]
            g.es["arrow_size"] = [{
                "provides": 0,
                "requires": 1,
                "extends": 1
                }[verb] for verb in g.es["verb"]]
            g.vs["size"] = [{
                "project":20,
                "skill":10,
                "state":30
                }[noun] for noun in g.vs["noun"]]
            self.graph = g
        return self.graph
        
    def render_graph(self):
        g = self.as_graph()
        graph_style = {
            "layout" : g.layout("fr"), 
            "vertex_label_size" : 12, 
            "vertex_label_dist" : 1, 
            "edge_label_size" : 8,
        }
        return igraph.plot(g,**graph_style)
        
    def build_path_to(self,goal_name,start=None,selected=None,max_loops=10):
        g = self.as_graph()
        
        # Get the desired ending node
        goal = g.vs.find(name=goal_name)
        
        # Find paths from zero knowledge by default
        if start is None:
            start = g.vs.find(name="root")
        
        # (re-)set graph state and list of selected nodes
        g.es["color"] = "gray"
        g.vs["label_color"] = "gray"
        g.es["weight"] = 0
        selected = {
            "nodes" : set([start.index,goal.index]),
            "paths" : [],
            }
            
        print "BUILDING LESSON PLAN..."
        loop = 0
        while True:    
            loop += 1
            
            # (re-)set map colors
            g.vs.select(color_eq="red")["color"] = "cyan"
            g.vs.select(label_color_eq="red")["label_color"] = "gray"
                
            # For each project in the selected set, look for requirements that are not not provided
            # by other projects in the set 
            unmet = set()
            for project in g.vs[selected["nodes"]].select(noun_eq="project"):
                project_unmet = [ r.index for r in g.vs.select(name_in=project["requires"]) if r.index not in selected["nodes"] ]
                if len(project_unmet) != 0:
                    print "  Pass %s: need to resolve unmet dependencies for '%s': %s" % (loop,project["name"],", ".join([g.vs[d]["name"] for d in project_unmet]))
                    unmet.update(project_unmet)
                    g.vs[project_unmet]["color"] = "red"
                    g.vs[project_unmet]["label_color"] = "red"
                    
            if loop >= max_loops:
                print "EMERGENCY BRAKE! Maximum iterations reached"
                break
                    
            # When all requirements are accounted for by projects in the set, we're done!
            if len(unmet) == 0:
                print "DONE! (passes: %s)" % loop
                break
            
            # Find the shortest path from start to each dependency.
            # Along the way, we add weights to encourage future paths to overlap as much as possible
            #print "   Getting paths for unmet dependencies:\n    %s" % "\n    ".join([g.vs[x]["name"] for x in unmet]) 
            paths = g.get_shortest_paths(start, unmet, weights="weight") 
            for path in paths:
                if path not in selected["paths"]:
                    selected["paths"].append(path)
                # Give edges that connect to the selected path a small bonus
                for project_on_path in g.vs[path].select(noun_eq="project"):
                    if project_on_path.index not in selected["nodes"]:
                        #print "  ADDING PROJECT: %s" % project_on_path["name"]
                        selected["nodes"].add(project_on_path.index)
                        for provides_edge in g.es.select(_source=project_on_path.index,verb_eq="provides"):
                            provides_skill = g.vs[provides_edge.target]
                            if provides_skill["noun"] != "skill":
                                continue
                            provides_edge["weight"] += 10
                            provides_edge["color"] = "green"
                            if provides_skill.index in unmet:
                                print "    Project '%s' teaches required skill '%s'" % (project_on_path["name"],provides_skill["name"])
                            else:
                                print "    Project '%s' adds extraneous skill '%s'" % (project_on_path["name"],provides_skill["name"])
                            selected["nodes"].add(provides_skill.index)
                # Give edges that are in the selected path a large bonus
                # and highlight them on the graph
                for path_taken in [ g.es[eid] for eid in g.get_eids(path=path) ]:
                    path_taken["weight"] += 50
                    path_taken["color"] = "green"
                    
        # Mark the final goal
        for e in g.es.select(_target=goal.index):
            e["color"] = "green"
        goal["color"] = "yellow"
        return selected
        
    def weight_by_relevance(self,skills):
        pass
            
    
    def get_skills(self,project_name,follow_extensions=False):
        project_data = self.projects_raw[project_name]
        provides = set()
        if project_data.has_key("provides"):
            provides.update(parse_skills(project_data["provides"]))
        requires = set()
        if project_data.has_key("requires"):
            requires.update(parse_skills(project_data["requires"]))
                            
        if follow_extensions and project_data.has_key("extends"):
            for extends in project_data["extends"]:
                (e_provides,e_requires) = self.get_skills(extends,follow_extensions)
                provides.update(e_provides)
                requires.update(e_requires)
                
        return (provides,requires)
    
    def get_projects_that_teach(self,skill):
        return self.projects_by_skill_provided.get(skill,{})
    
    def get_projects_that_assess(self,skill):
        return self.projects_by_skill_required.get(skill,{})            
            
    def _index_projects(self,projects=None,follow_extensions=False):
        if projects is None:
            projects = self.projects_raw
         
        skills_provided_by_project = {}
        skills_required_by_project = {}
        projects_by_skill_required = {}
        projects_by_skill_provided = {}
        projects_that_extend = {}
        projects_extended_by = {}
        
        for project_name,props in projects.items():
            (provides,requires) = self.get_skills(project_name,follow_extensions)
            
            skills_provided_by_project[project_name] = set()
            for skill in provides:
                skills_provided_by_project[project_name].add(skill)
                if not projects_by_skill_provided.has_key(skill):
                    projects_by_skill_provided[skill] = set()
                projects_by_skill_provided[skill].add(project_name)
                
            skills_required_by_project[project_name] = set()
            for skill in requires:
                skills_required_by_project[project_name].add(skill)
                if not projects_by_skill_required.has_key(skill):
                    projects_by_skill_required[skill] = set()
                projects_by_skill_required[skill].add(project_name)
                    
            projects_extended_by[project_name] = set()
            if props.has_key('extends'):
                for extends in (props['extends']):
                    projects_extended_by[project_name].add(extends)
                    if not projects_that_extend.has_key(extends):
                        projects_that_extend[extends] = set()
                    projects_that_extend[extends].add(project_name)
         
        return(skills_provided_by_project,
            skills_required_by_project,
            projects_by_skill_required,
            projects_by_skill_provided,
            projects_that_extend,
            projects_extended_by)
            
    def assessments_for_skills(self,skills):   
        projects = set()
        target_skills = set()
        orphan_skills = set()
        for skill in parse_skills(skills):
            # Get all projects that require this skill
            candidate_projects = self.get_projects_that_assess(skill)
            if len(candidate_projects) > 0:
                target_skills.add(skill)
                projects.update(candidate_projects)
            else:
                print "XXX ORPHAN: '%s'" % skill
                orphan_skills.add(skill)
                
        # Look over the list of projects and their skills, using the
        # scoring algorithm to drop one each time, for as many
        # iterations as possible. The range() here is just a cheap
        # way to avoid infinite loops if something goes wrong 
        max_loops = len(projects)
        for loop in range(0, max_loops):             
            projects_by_score = {}
            for project_name in projects:
                (provides,requires) = self.get_skills(project_name)
                relevant = target_skills.intersection(requires)
                
                # How many assessed skills are in the requested list?
                relevance_modifier = float(len(relevant)) / len(requires)
                
                # How many assessed skills are shared with how many projects?
                redundancy_modifier = 0
                uniqueness_modifier = -1
                for skill in relevant:
                    overlap = projects.intersection(self.get_projects_that_assess(skill))
                    redundancy_modifier += len(overlap) - 1
                    if redundancy_modifier == 0:
                        uniqueness_modifier = 1
                projects_by_score[project_name] = uniqueness_modifier * redundancy_modifier * relevance_modifier
                
            print "XX SCOOOORES: %s" % projects_by_score

            # Count backwards from the highest score to find the highest
            # negative score, if one exists. That is, the project with no 
            # unique skills and the least overlap with other projects.
            remove_me = None
            
            print "XXX SCORES = %s" % projects_by_score
            for score in reversed(sorted(projects_by_score.keys())):
                if score < 0:
                    remove_me = projects_by_score[score].pop()
                    break

            # If there are no negative scores, then every remaining project
            # has at least one unique skill and cannot be removed.
            if remove_me is None:
                print "*** Nothing left to remove ***"
                break
            print self.explain()

            # Otherwise, remove the first project associated with the selected score,
            # Then repeat the loop to re-calculate/remove until all remaining
            # projects have at least one unique skill or we pass the loop limit.
            print "*** Removing '%s' and re-calculating... ***\n" % remove_me
            projects.remove(remove_me) 
        return projects
            
    def explain(self):
        report = []
        indent = "    "
        scores = reversed(sorted(self.projects_by_score.keys()))
        for score in scores:
            for project in self.projects_by_score[score]:
                dists = self.project_overlaps[project]
                report.append("SCORE %s: %s" % (score, project))
                for frequency in sorted(dists.keys()):
                    skills = dists[frequency]
                    if frequency == 1:
                        report.append(indent + "%s unique skill(s)" % (len(skills)))
                    else:
                        report.append(indent + "%s skill(s) shared with %s other project(s):" % (len(skills),frequency-1))
                    for skill in skills:
                        report.append(indent * 2 + skill)
                        shared_with = [ shared for shared in self.projects_by_skill[skill] if shared != project ]
                        if len(shared_with) > 0:
                            report.append(indent * 3 + "Shared with:")
                            report.append("\n".join([ indent * 4 + shared for shared in shared_with ]))
                report.append("")
        return "\n".join(report) + "\n"
    
    
if __name__ == "__main__":
    swagifacts_yml = open("swagifacts.yml","r").read().lower()
    library = ProjectLibrary(yaml.load(swagifacts_yml))   
    python_basics = [
     "Script: executable, importable, exit",
     "Control: if, else",
     "Input: CLI menu, file, XML",
     "Output: print, file, stderr",
     "Exception: define, raise, catch",
     "File: open, write, close",
     "Math: arithmetic, modulo",
    ]
    
    print library.as_graph()
    #lp = library.assessments_for_skills(["control: if","output:file"])
    #print str(lp)
