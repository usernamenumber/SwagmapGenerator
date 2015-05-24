#!/usr/bin/python
import yaml
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
    def __init__(self,projects={}):
        self.skills_provided_by_project = {}
        self.projects_by_skill_provided = {}
        self.skills_required_by_project = {}
        self.projects_by_skill_required = {}
        self.project_dependencies = {}
        self.projects_raw = {}
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
    lp = library.assessments_for_skills(["control: if","output:file"])
    print str(lp)
